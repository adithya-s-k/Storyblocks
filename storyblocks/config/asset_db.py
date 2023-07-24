from storyblocks.database.db_document import TinyMongoDocument
# from storyblocks.audio.audio_utils import  downloadYoutubeAudio, getAssetDuration
import pandas as pd
import shutil
import os
import re
import time
import base64
from datetime import datetime
audio_extensions = [".mp3", ".m4a", ".wav", ".flac", ".aac", ".ogg", ".wma", ".opus"]
image_extensions = [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp"]
video_extensions = [".mp4", ".mkv", ".flv", ".avi", ".mov", ".wmv", ".webm", ".m4v"]
TEMPLATE_ASSETS_DB_PATH = '.database/template_asset_db.json'
ASSETS_DB_PATH = '.database/asset_db.json'
class AssetDatabase:
    def __init__(self):
        if not (os.path.exists(ASSETS_DB_PATH)) and os.path.exists(TEMPLATE_ASSETS_DB_PATH):
            shutil.copy(TEMPLATE_ASSETS_DB_PATH, ASSETS_DB_PATH)
            
        self.local_assets = TinyMongoDocument("asset_db", "asset_collection", "local_assets", create=True)
        self.remote_assets = TinyMongoDocument("asset_db", "asset_collection", "remote_assets", create=True)
    
    def asset_exists(self, name):
        local_assets = self.local_assets._get()
        if name in local_assets:
            return True
        remote_assets = self.remote_assets._get()
        if name in remote_assets:
            return True
        return False

    def add_local_asset(self, name, type, path):
        """Add a local asset to the database."""
        self.local_assets._save({
            name: {
                "type": type,
                "path": path,
                "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        })

    def add_remote_asset(self, name, type, url):
        """Add a remote asset to the database."""
        self.remote_assets._save({
            name: {
                "type": type,
                "url": url,
                "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        })

    def remove_asset(self, name):
        """Remove an asset from the database."""
        # Check if the asset exists in local assets
        local_assets = self.local_assets._get()
        if name in local_assets:
            if (not 'required' in local_assets[name]):
                try:
                    os.remove(local_assets[name]['path'])
                except Exception as e:
                    print(e)
                self.local_assets._delete(name)

        # Check if the asset exists in remote assets
        remote_assets = self.remote_assets._get()
        if name in remote_assets:
            self.remote_assets._delete(name)

        # # If the asset does not exist in the database
        # raise ValueError(f"Asset '{name}' does not exist in the database.")

    def get_df(self):
        """Returns a pandas DataFrame with specific asset details."""

        remote_assets = self.remote_assets._get()

        # Prepare data for DataFrame
        data = []
        remote_items = remote_assets.items()
        for key, asset in remote_items:
            ts = asset['ts'] if 'ts' in asset else None
            data.append({'name': key, 'type': asset['type'], 'link': asset['url'], 'source': 'youtube', 'ts': ts})

        # Create DataFrame
        df = pd.DataFrame(data)

        # Sort DataFrame by ts
        df.sort_values(by='ts', ascending=False, inplace=True)
        df = df.drop(columns='ts')
        return df

    def sync_local_assets(self):
        """Loads all local assets from the static-assets folder into the database"""
        local_paths = []
        local_assets = self.local_assets._get()
        for key in local_assets:
            asset = local_assets[key]
            filePath = asset['path']
            if not os.path.exists(filePath):
                self.local_assets._delete(key)
            else:
                local_paths.append(filePath)

        folder_path = 'public'
        for foldername, subfolders, filenames in os.walk(folder_path):
            for filename in filenames:
                file_path = os.path.join(foldername, filename).replace("\\", "/")
                if not file_path in local_paths:
                    file_ext = os.path.splitext(file_path)[1]
                    if file_ext in audio_extensions:
                        asset_type = 'audio'
                    elif file_ext in image_extensions:
                        asset_type = 'image'
                    elif file_ext in video_extensions:
                        asset_type = 'video'
                    else:
                        asset_type = 'other'
                    self.local_assets._save({f'{filename.split(".")[0]}': {"path": file_path, "type": asset_type,"ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}})
