from .k_diffusion import sampling as k_diffusion_sampling
from .k_diffusion import external as k_diffusion_external
from .extra_samplers import uni_pc
import torch
import enum
from fcbh import model_management
from .ldm.models.diffusion.ddim import DDIMSampler
from .ldm.modules.diffusionmodules.util import make_ddim_timesteps
import math
from fcbh import model_base
import fcbh.utils
import fcbh.conds


#The main sampling function shared by all the samplers
#Returns predicted noise
def sampling_function(model_function, x, timestep, uncond, cond, cond_scale, model_options={}, seed=None):
        def get_area_and_mult(conds, x_in, timestep_in):
            area = (x_in.shape[2], x_in.shape[3], 0, 0)
            strength = 1.0

            if 'timestep_start' in conds:
                timestep_start = conds['timestep_start']
                if timestep_in[0] > timestep_start:
                    return None
            if 'timestep_end' in conds:
                timestep_end = conds['timestep_end']
                if timestep_in[0] < timestep_end:
                    return None
            if 'area' in conds:
                area = conds['area']
            if 'strength' in conds:
                strength = conds['strength']

            input_x = x_in[:,:,area[2]:area[0] + area[2],area[3]:area[1] + area[3]]
            if 'mask' in conds:
                # Scale the mask to the size of the input
                # The mask should have been resized as we began the sampling process
                mask_strength = 1.0
                if "mask_strength" in conds:
                    mask_strength = conds["mask_strength"]
                mask = conds['mask']
                assert(mask.shape[1] == x_in.shape[2])
                assert(mask.shape[2] == x_in.shape[3])
                mask = mask[:,area[2]:area[0] + area[2],area[3]:area[1] + area[3]] * mask_strength
                mask = mask.unsqueeze(1).repeat(input_x.shape[0] // mask.shape[0], input_x.shape[1], 1, 1)
            else:
                mask = torch.ones_like(input_x)
            mult = mask * strength

            if 'mask' not in conds:
                rr = 8
                if area[2] != 0:
                    for t in range(rr):
                        mult[:,:,t:1+t,:] *= ((1.0/rr) * (t + 1))
                if (area[0] + area[2]) < x_in.shape[2]:
                    for t in range(rr):
                        mult[:,:,area[0] - 1 - t:area[0] - t,:] *= ((1.0/rr) * (t + 1))
                if area[3] != 0:
                    for t in range(rr):
                        mult[:,:,:,t:1+t] *= ((1.0/rr) * (t + 1))
                if (area[1] + area[3]) < x_in.shape[3]:
                    for t in range(rr):
                        mult[:,:,:,area[1] - 1 - t:area[1] - t] *= ((1.0/rr) * (t + 1))

            conditionning = {}
            model_conds = conds["model_conds"]
            for c in model_conds:
                conditionning[c] = model_conds[c].process_cond(batch_size=x_in.shape[0], device=x_in.device, area=area)

            control = None
            if 'control' in conds:
                control = conds['control']

            patches = None
            if 'gligen' in conds:
                gligen = conds['gligen']
                patches = {}
                gligen_type = gligen[0]
                gligen_model = gligen[1]
                if gligen_type == "position":
                    gligen_patch = gligen_model.model.set_position(input_x.shape, gligen[2], input_x.device)
                else:
                    gligen_patch = gligen_model.model.set_empty(input_x.shape, input_x.device)

                patches['middle_patch'] = [gligen_patch]

            return (input_x, mult, conditionning, area, control, patches)

        def cond_equal_size(c1, c2):
            if c1 is c2:
                return True
            if c1.keys() != c2.keys():
                return False
            for k in c1:
                if not c1[k].can_concat(c2[k]):
                    return False
            return True

        def can_concat_cond(c1, c2):
            if c1[0].shape != c2[0].shape:
                return False

            #control
            if (c1[4] is None) != (c2[4] is None):
                return False
            if c1[4] is not None:
                if c1[4] is not c2[4]:
                    return False

            #patches
            if (c1[5] is None) != (c2[5] is None):
                return False
            if (c1[5] is not None):
                if c1[5] is not c2[5]:
                    return False

            return cond_equal_size(c1[2], c2[2])

        def cond_cat(c_list):
            c_crossattn = []
            c_concat = []
            c_adm = []
            crossattn_max_len = 0

            temp = {}
            for x in c_list:
                for k in x:
                    cur = temp.get(k, [])
                    cur.append(x[k])
                    temp[k] = cur

            out = {}
            for k in temp:
                conds = temp[k]
                out[k] = conds[0].concat(conds[1:])

            return out

        def calc_cond_uncond_batch(model_function, cond, uncond, x_in, timestep, max_total_area, model_options):
            out_cond = torch.zeros_like(x_in)
            out_count = torch.ones_like(x_in)/100000.0

            out_uncond = torch.zeros_like(x_in)
            out_uncond_count = torch.ones_like(x_in)/100000.0

            COND = 0
            UNCOND = 1

            to_run = []
            for x in cond:
                p = get_area_and_mult(x, x_in, timestep)
                if p is None:
                    continue

                to_run += [(p, COND)]
            if uncond is not None:
                for x in uncond:
                    p = get_area_and_mult(x, x_in, timestep)
                    if p is None:
                        continue

                    to_run += [(p, UNCOND)]

            while len(to_run) > 0:
                first = to_run[0]
                first_shape = first[0][0].shape
                to_batch_temp = []
                for x in range(len(to_run)):
                    if can_concat_cond(to_run[x][0], first[0]):
                        to_batch_temp += [x]

                to_batch_temp.reverse()
                to_batch = to_batch_temp[:1]

                for i in range(1, len(to_batch_temp) + 1):
                    batch_amount = to_batch_temp[:len(to_batch_temp)//i]
                    if (len(batch_amount) * first_shape[0] * first_shape[2] * first_shape[3] < max_total_area):
                        to_batch = batch_amount
                        break

                input_x = []
                mult = []
                c = []
                cond_or_uncond = []
                area = []
                control = None
                patches = None
                for x in to_batch:
                    o = to_run.pop(x)
                    p = o[0]
                    input_x += [p[0]]
                    mult += [p[1]]
                    c += [p[2]]
                    area += [p[3]]
                    cond_or_uncond += [o[1]]
                    control = p[4]
                    patches = p[5]

                batch_chunks = len(cond_or_uncond)
                input_x = torch.cat(input_x)
                c = cond_cat(c)
                timestep_ = torch.cat([timestep] * batch_chunks)

                if control is not None:
                    c['control'] = control.get_control(input_x, timestep_, c, len(cond_or_uncond))

                transformer_options = {}
                if 'transformer_options' in model_options:
                    transformer_options = model_options['transformer_options'].copy()

                if patches is not None:
                    if "patches" in transformer_options:
                        cur_patches = transformer_options["patches"].copy()
                        for p in patches:
                            if p in cur_patches:
                                cur_patches[p] = cur_patches[p] + patches[p]
                            else:
                                cur_patches[p] = patches[p]
                    else:
                        transformer_options["patches"] = patches

                transformer_options["cond_or_uncond"] = cond_or_uncond[:]
                c['transformer_options'] = transformer_options

                if 'model_function_wrapper' in model_options:
                    output = model_options['model_function_wrapper'](model_function, {"input": input_x, "timestep": timestep_, "c": c, "cond_or_uncond": cond_or_uncond}).chunk(batch_chunks)
                else:
                    output = model_function(input_x, timestep_, **c).chunk(batch_chunks)
                del input_x

                for o in range(batch_chunks):
                    if cond_or_uncond[o] == COND:
                        out_cond[:,:,area[o][2]:area[o][0] + area[o][2],area[o][3]:area[o][1] + area[o][3]] += output[o] * mult[o]
                        out_count[:,:,area[o][2]:area[o][0] + area[o][2],area[o][3]:area[o][1] + area[o][3]] += mult[o]
                    else:
                        out_uncond[:,:,area[o][2]:area[o][0] + area[o][2],area[o][3]:area[o][1] + area[o][3]] += output[o] * mult[o]
                        out_uncond_count[:,:,area[o][2]:area[o][0] + area[o][2],area[o][3]:area[o][1] + area[o][3]] += mult[o]
                del mult

            out_cond /= out_count
            del out_count
            out_uncond /= out_uncond_count
            del out_uncond_count

            return out_cond, out_uncond


        max_total_area = model_management.maximum_batch_area()
        if math.isclose(cond_scale, 1.0):
            uncond = None

        cond, uncond = calc_cond_uncond_batch(model_function, cond, uncond, x, timestep, max_total_area, model_options)
        if "sampler_cfg_function" in model_options:
            args = {"cond": cond, "uncond": uncond, "cond_scale": cond_scale, "timestep": timestep}
            return model_options["sampler_cfg_function"](args)
        else:
            return uncond + (cond - uncond) * cond_scale


class CompVisVDenoiser(k_diffusion_external.DiscreteVDDPMDenoiser):
    def __init__(self, model, quantize=False, device='cpu'):
        super().__init__(model, model.alphas_cumprod, quantize=quantize)

    def get_v(self, x, t, cond, **kwargs):
        return self.inner_model.apply_model(x, t, cond, **kwargs)


class CFGNoisePredictor(torch.nn.Module):
    def __init__(self, model):
        super().__init__()
        self.inner_model = model
        self.alphas_cumprod = model.alphas_cumprod
    def apply_model(self, x, timestep, cond, uncond, cond_scale, model_options={}, seed=None):
        out = sampling_function(self.inner_model.apply_model, x, timestep, uncond, cond, cond_scale, model_options=model_options, seed=seed)
        return out


class KSamplerX0Inpaint(torch.nn.Module):
    def __init__(self, model):
        super().__init__()
        self.inner_model = model
    def forward(self, x, sigma, uncond, cond, cond_scale, denoise_mask, model_options={}, seed=None):
        if denoise_mask is not None:
            latent_mask = 1. - denoise_mask
            x = x * denoise_mask + (self.latent_image + self.noise * sigma.reshape([sigma.shape[0]] + [1] * (len(self.noise.shape) - 1))) * latent_mask
        out = self.inner_model(x, sigma, cond=cond, uncond=uncond, cond_scale=cond_scale, model_options=model_options, seed=seed)
        if denoise_mask is not None:
            out *= denoise_mask

        if denoise_mask is not None:
            out += self.latent_image * latent_mask
        return out

def simple_scheduler(model, steps):
    sigs = []
    ss = len(model.sigmas) / steps
    for x in range(steps):
        sigs += [float(model.sigmas[-(1 + int(x * ss))])]
    sigs += [0.0]
    return torch.FloatTensor(sigs)

def ddim_scheduler(model, steps):
    sigs = []
    ddim_timesteps = make_ddim_timesteps(ddim_discr_method="uniform", num_ddim_timesteps=steps, num_ddpm_timesteps=model.inner_model.inner_model.num_timesteps, verbose=False)
    for x in range(len(ddim_timesteps) - 1, -1, -1):
        ts = ddim_timesteps[x]
        if ts > 999:
            ts = 999
        sigs.append(model.t_to_sigma(torch.tensor(ts)))
    sigs += [0.0]
    return torch.FloatTensor(sigs)

def sgm_scheduler(model, steps):
    sigs = []
    timesteps = torch.linspace(model.inner_model.inner_model.num_timesteps - 1, 0, steps + 1)[:-1].type(torch.int)
    for x in range(len(timesteps)):
        ts = timesteps[x]
        if ts > 999:
            ts = 999
        sigs.append(model.t_to_sigma(torch.tensor(ts)))
    sigs += [0.0]
    return torch.FloatTensor(sigs)

def get_mask_aabb(masks):
    if masks.numel() == 0:
        return torch.zeros((0, 4), device=masks.device, dtype=torch.int)

    b = masks.shape[0]

    bounding_boxes = torch.zeros((b, 4), device=masks.device, dtype=torch.int)
    is_empty = torch.zeros((b), device=masks.device, dtype=torch.bool)
    for i in range(b):
        mask = masks[i]
        if mask.numel() == 0:
            continue
        if torch.max(mask != 0) == False:
            is_empty[i] = True
            continue
        y, x = torch.where(mask)
        bounding_boxes[i, 0] = torch.min(x)
        bounding_boxes[i, 1] = torch.min(y)
        bounding_boxes[i, 2] = torch.max(x)
        bounding_boxes[i, 3] = torch.max(y)

    return bounding_boxes, is_empty

def resolve_areas_and_cond_masks(conditions, h, w, device):
    # We need to decide on an area outside the sampling loop in order to properly generate opposite areas of equal sizes.
    # While we're doing this, we can also resolve the mask device and scaling for performance reasons
    for i in range(len(conditions)):
        c = conditions[i]
        if 'area' in c:
            area = c['area']
            if area[0] == "percentage":
                modified = c.copy()
                area = (max(1, round(area[1] * h)), max(1, round(area[2] * w)), round(area[3] * h), round(area[4] * w))
                modified['area'] = area
                c = modified
                conditions[i] = c

        if 'mask' in c:
            mask = c['mask']
            mask = mask.to(device=device)
            modified = c.copy()
            if len(mask.shape) == 2:
                mask = mask.unsqueeze(0)
            if mask.shape[1] != h or mask.shape[2] != w:
                mask = torch.nn.functional.interpolate(mask.unsqueeze(1), size=(h, w), mode='bilinear', align_corners=False).squeeze(1)

            if modified.get("set_area_to_bounds", False):
                bounds = torch.max(torch.abs(mask),dim=0).values.unsqueeze(0)
                boxes, is_empty = get_mask_aabb(bounds)
                if is_empty[0]:
                    # Use the minimum possible size for efficiency reasons. (Since the mask is all-0, this becomes a noop anyway)
                    modified['area'] = (8, 8, 0, 0)
                else:
                    box = boxes[0]
                    H, W, Y, X = (box[3] - box[1] + 1, box[2] - box[0] + 1, box[1], box[0])
                    H = max(8, H)
                    W = max(8, W)
                    area = (int(H), int(W), int(Y), int(X))
                    modified['area'] = area

            modified['mask'] = mask
            conditions[i] = modified

def create_cond_with_same_area_if_none(conds, c):
    if 'area' not in c:
        return

    c_area = c['area']
    smallest = None
    for x in conds:
        if 'area' in x:
            a = x['area']
            if c_area[2] >= a[2] and c_area[3] >= a[3]:
                if a[0] + a[2] >= c_area[0] + c_area[2]:
                    if a[1] + a[3] >= c_area[1] + c_area[3]:
                        if smallest is None:
                            smallest = x
                        elif 'area' not in smallest:
                            smallest = x
                        else:
                            if smallest['area'][0] * smallest['area'][1] > a[0] * a[1]:
                                smallest = x
        else:
            if smallest is None:
                smallest = x
    if smallest is None:
        return
    if 'area' in smallest:
        if smallest['area'] == c_area:
            return

    out = c.copy()
    out['model_conds'] = smallest['model_conds'].copy() #TODO: which fields should be copied?
    conds += [out]

def calculate_start_end_timesteps(model, conds):
    for t in range(len(conds)):
        x = conds[t]

        timestep_start = None
        timestep_end = None
        if 'start_percent' in x:
            timestep_start = model.sigma_to_t(model.t_to_sigma(torch.tensor(x['start_percent'] * 999.0)))
        if 'end_percent' in x:
            timestep_end = model.sigma_to_t(model.t_to_sigma(torch.tensor(x['end_percent'] * 999.0)))

        if (timestep_start is not None) or (timestep_end is not None):
            n = x.copy()
            if (timestep_start is not None):
                n['timestep_start'] = timestep_start
            if (timestep_end is not None):
                n['timestep_end'] = timestep_end
            conds[t] = n

def pre_run_control(model, conds):
    for t in range(len(conds)):
        x = conds[t]

        timestep_start = None
        timestep_end = None
        percent_to_timestep_function = lambda a: model.sigma_to_t(model.t_to_sigma(torch.tensor(a) * 999.0))
        if 'control' in x:
            x['control'].pre_run(model.inner_model.inner_model, percent_to_timestep_function)

def apply_empty_x_to_equal_area(conds, uncond, name, uncond_fill_func):
    cond_cnets = []
    cond_other = []
    uncond_cnets = []
    uncond_other = []
    for t in range(len(conds)):
        x = conds[t]
        if 'area' not in x:
            if name in x and x[name] is not None:
                cond_cnets.append(x[name])
            else:
                cond_other.append((x, t))
    for t in range(len(uncond)):
        x = uncond[t]
        if 'area' not in x:
            if name in x and x[name] is not None:
                uncond_cnets.append(x[name])
            else:
                uncond_other.append((x, t))

    if len(uncond_cnets) > 0:
        return

    for x in range(len(cond_cnets)):
        temp = uncond_other[x % len(uncond_other)]
        o = temp[0]
        if name in o and o[name] is not None:
            n = o.copy()
            n[name] = uncond_fill_func(cond_cnets, x)
            uncond += [n]
        else:
            n = o.copy()
            n[name] = uncond_fill_func(cond_cnets, x)
            uncond[temp[1]] = n

def encode_model_conds(model_function, conds, noise, device, prompt_type, **kwargs):
    for t in range(len(conds)):
        x = conds[t]
        params = x.copy()
        params["device"] = device
        params["noise"] = noise
        params["width"] = params.get("width", noise.shape[3] * 8)
        params["height"] = params.get("height", noise.shape[2] * 8)
        params["prompt_type"] = params.get("prompt_type", prompt_type)
        for k in kwargs:
            if k not in params:
                params[k] = kwargs[k]

        out = model_function(**params)
        x = x.copy()
        model_conds = x['model_conds'].copy()
        for k in out:
            model_conds[k] = out[k]
        x['model_conds'] = model_conds
        conds[t] = x
    return conds

class Sampler:
    def sample(self):
        pass

    def max_denoise(self, model_wrap, sigmas):
        return math.isclose(float(model_wrap.sigma_max), float(sigmas[0]), rel_tol=1e-05)

class DDIM(Sampler):
    def sample(self, model_wrap, sigmas, extra_args, callback, noise, latent_image=None, denoise_mask=None, disable_pbar=False):
        timesteps = []
        for s in range(sigmas.shape[0]):
            timesteps.insert(0, model_wrap.sigma_to_discrete_timestep(sigmas[s]))
        noise_mask = None
        if denoise_mask is not None:
            noise_mask = 1.0 - denoise_mask

        ddim_callback = None
        if callback is not None:
            total_steps = len(timesteps) - 1
            ddim_callback = lambda pred_x0, i: callback(i, pred_x0, None, total_steps)

        max_denoise = self.max_denoise(model_wrap, sigmas)

        ddim_sampler = DDIMSampler(model_wrap.inner_model.inner_model, device=noise.device)
        ddim_sampler.make_schedule_timesteps(ddim_timesteps=timesteps, verbose=False)
        z_enc = ddim_sampler.stochastic_encode(latent_image, torch.tensor([len(timesteps) - 1] * noise.shape[0]).to(noise.device), noise=noise, max_denoise=max_denoise)
        samples, _ = ddim_sampler.sample_custom(ddim_timesteps=timesteps,
                                                batch_size=noise.shape[0],
                                                shape=noise.shape[1:],
                                                verbose=False,
                                                eta=0.0,
                                                x_T=z_enc,
                                                x0=latent_image,
                                                img_callback=ddim_callback,
                                                denoise_function=model_wrap.predict_eps_discrete_timestep,
                                                extra_args=extra_args,
                                                mask=noise_mask,
                                                to_zero=sigmas[-1]==0,
                                                end_step=sigmas.shape[0] - 1,
                                                disable_pbar=disable_pbar)
        return samples

class UNIPC(Sampler):
    def sample(self, model_wrap, sigmas, extra_args, callback, noise, latent_image=None, denoise_mask=None, disable_pbar=False):
        return uni_pc.sample_unipc(model_wrap, noise, latent_image, sigmas, sampling_function=sampling_function, max_denoise=self.max_denoise(model_wrap, sigmas), extra_args=extra_args, noise_mask=denoise_mask, callback=callback, disable=disable_pbar)

class UNIPCBH2(Sampler):
    def sample(self, model_wrap, sigmas, extra_args, callback, noise, latent_image=None, denoise_mask=None, disable_pbar=False):
        return uni_pc.sample_unipc(model_wrap, noise, latent_image, sigmas, sampling_function=sampling_function, max_denoise=self.max_denoise(model_wrap, sigmas), extra_args=extra_args, noise_mask=denoise_mask, callback=callback, variant='bh2', disable=disable_pbar)

KSAMPLER_NAMES = ["euler", "euler_ancestral", "heun", "dpm_2", "dpm_2_ancestral",
                  "lms", "dpm_fast", "dpm_adaptive", "dpmpp_2s_ancestral", "dpmpp_sde", "dpmpp_sde_gpu",
                  "dpmpp_2m", "dpmpp_2m_sde", "dpmpp_2m_sde_gpu", "dpmpp_3m_sde", "dpmpp_3m_sde_gpu", "ddpm"]

def ksampler(sampler_name, extra_options={}):
    class KSAMPLER(Sampler):
        def sample(self, model_wrap, sigmas, extra_args, callback, noise, latent_image=None, denoise_mask=None, disable_pbar=False):
            extra_args["denoise_mask"] = denoise_mask
            model_k = KSamplerX0Inpaint(model_wrap)
            model_k.latent_image = latent_image
            model_k.noise = noise

            if self.max_denoise(model_wrap, sigmas):
                noise = noise * torch.sqrt(1.0 + sigmas[0] ** 2.0)
            else:
                noise = noise * sigmas[0]

            k_callback = None
            total_steps = len(sigmas) - 1
            if callback is not None:
                k_callback = lambda x: callback(x["i"], x["denoised"], x["x"], total_steps)

            sigma_min = sigmas[-1]
            if sigma_min == 0:
                sigma_min = sigmas[-2]

            if latent_image is not None:
                noise += latent_image
            if sampler_name == "dpm_fast":
                samples = k_diffusion_sampling.sample_dpm_fast(model_k, noise, sigma_min, sigmas[0], total_steps, extra_args=extra_args, callback=k_callback, disable=disable_pbar)
            elif sampler_name == "dpm_adaptive":
                samples = k_diffusion_sampling.sample_dpm_adaptive(model_k, noise, sigma_min, sigmas[0], extra_args=extra_args, callback=k_callback, disable=disable_pbar)
            else:
                samples = getattr(k_diffusion_sampling, "sample_{}".format(sampler_name))(model_k, noise, sigmas, extra_args=extra_args, callback=k_callback, disable=disable_pbar, **extra_options)
            return samples
    return KSAMPLER

def wrap_model(model):
    model_denoise = CFGNoisePredictor(model)
    if model.model_type == model_base.ModelType.V_PREDICTION:
        model_wrap = CompVisVDenoiser(model_denoise, quantize=True)
    else:
        model_wrap = k_diffusion_external.CompVisDenoiser(model_denoise, quantize=True)
    return model_wrap

def sample(model, noise, positive, negative, cfg, device, sampler, sigmas, model_options={}, latent_image=None, denoise_mask=None, callback=None, disable_pbar=False, seed=None):
    positive = positive[:]
    negative = negative[:]

    resolve_areas_and_cond_masks(positive, noise.shape[2], noise.shape[3], device)
    resolve_areas_and_cond_masks(negative, noise.shape[2], noise.shape[3], device)

    model_wrap = wrap_model(model)

    calculate_start_end_timesteps(model_wrap, negative)
    calculate_start_end_timesteps(model_wrap, positive)

    #make sure each cond area has an opposite one with the same area
    for c in positive:
        create_cond_with_same_area_if_none(negative, c)
    for c in negative:
        create_cond_with_same_area_if_none(positive, c)

    pre_run_control(model_wrap, negative + positive)

    apply_empty_x_to_equal_area(list(filter(lambda c: c.get('control_apply_to_uncond', False) == True, positive)), negative, 'control', lambda cond_cnets, x: cond_cnets[x])
    apply_empty_x_to_equal_area(positive, negative, 'gligen', lambda cond_cnets, x: cond_cnets[x])

    if latent_image is not None:
        latent_image = model.process_latent_in(latent_image)

    if hasattr(model, 'extra_conds'):
        positive = encode_model_conds(model.extra_conds, positive, noise, device, "positive", latent_image=latent_image, denoise_mask=denoise_mask)
        negative = encode_model_conds(model.extra_conds, negative, noise, device, "negative", latent_image=latent_image, denoise_mask=denoise_mask)

    extra_args = {"cond":positive, "uncond":negative, "cond_scale": cfg, "model_options": model_options, "seed":seed}

    samples = sampler.sample(model_wrap, sigmas, extra_args, callback, noise, latent_image, denoise_mask, disable_pbar)
    return model.process_latent_out(samples.to(torch.float32))

SCHEDULER_NAMES = ["normal", "karras", "exponential", "sgm_uniform", "simple", "ddim_uniform"]
SAMPLER_NAMES = KSAMPLER_NAMES + ["ddim", "uni_pc", "uni_pc_bh2"]

def calculate_sigmas_scheduler(model, scheduler_name, steps):
    model_wrap = wrap_model(model)
    if scheduler_name == "karras":
        sigmas = k_diffusion_sampling.get_sigmas_karras(n=steps, sigma_min=float(model_wrap.sigma_min), sigma_max=float(model_wrap.sigma_max))
    elif scheduler_name == "exponential":
        sigmas = k_diffusion_sampling.get_sigmas_exponential(n=steps, sigma_min=float(model_wrap.sigma_min), sigma_max=float(model_wrap.sigma_max))
    elif scheduler_name == "normal":
        sigmas = model_wrap.get_sigmas(steps)
    elif scheduler_name == "simple":
        sigmas = simple_scheduler(model_wrap, steps)
    elif scheduler_name == "ddim_uniform":
        sigmas = ddim_scheduler(model_wrap, steps)
    elif scheduler_name == "sgm_uniform":
        sigmas = sgm_scheduler(model_wrap, steps)
    else:
        print("error invalid scheduler", self.scheduler)
    return sigmas

def sampler_class(name):
    if name == "uni_pc":
        sampler = UNIPC
    elif name == "uni_pc_bh2":
        sampler = UNIPCBH2
    elif name == "ddim":
        sampler = DDIM
    else:
        sampler = ksampler(name)
    return sampler

class KSampler:
    SCHEDULERS = SCHEDULER_NAMES
    SAMPLERS = SAMPLER_NAMES

    def __init__(self, model, steps, device, sampler=None, scheduler=None, denoise=None, model_options={}):
        self.model = model
        self.device = device
        if scheduler not in self.SCHEDULERS:
            scheduler = self.SCHEDULERS[0]
        if sampler not in self.SAMPLERS:
            sampler = self.SAMPLERS[0]
        self.scheduler = scheduler
        self.sampler = sampler
        self.set_steps(steps, denoise)
        self.denoise = denoise
        self.model_options = model_options

    def calculate_sigmas(self, steps):
        sigmas = None

        discard_penultimate_sigma = False
        if self.sampler in ['dpm_2', 'dpm_2_ancestral', 'uni_pc', 'uni_pc_bh2']:
            steps += 1
            discard_penultimate_sigma = True

        sigmas = calculate_sigmas_scheduler(self.model, self.scheduler, steps)

        if discard_penultimate_sigma:
            sigmas = torch.cat([sigmas[:-2], sigmas[-1:]])
        return sigmas

    def set_steps(self, steps, denoise=None):
        self.steps = steps
        if denoise is None or denoise > 0.9999:
            self.sigmas = self.calculate_sigmas(steps).to(self.device)
        else:
            new_steps = int(steps/denoise)
            sigmas = self.calculate_sigmas(new_steps).to(self.device)
            self.sigmas = sigmas[-(steps + 1):]

    def sample(self, noise, positive, negative, cfg, latent_image=None, start_step=None, last_step=None, force_full_denoise=False, denoise_mask=None, sigmas=None, callback=None, disable_pbar=False, seed=None):
        if sigmas is None:
            sigmas = self.sigmas

        if last_step is not None and last_step < (len(sigmas) - 1):
            sigmas = sigmas[:last_step + 1]
            if force_full_denoise:
                sigmas[-1] = 0

        if start_step is not None:
            if start_step < (len(sigmas) - 1):
                sigmas = sigmas[start_step:]
            else:
                if latent_image is not None:
                    return latent_image
                else:
                    return torch.zeros_like(noise)

        sampler = sampler_class(self.sampler)

        return sample(self.model, noise, positive, negative, cfg, self.device, sampler(), sigmas, self.model_options, latent_image=latent_image, denoise_mask=denoise_mask, callback=callback, disable_pbar=disable_pbar, seed=seed)
