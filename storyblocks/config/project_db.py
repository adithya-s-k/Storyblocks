from storyblocks.database.db_document import TINY_MONGO_DATABASE, TinyMongoDocument

PROJECT_DOC_MANAGER = TinyMongoDocument("project_db", "project_collection", "project_doc", create=True)

def get_project_name():
    return PROJECT_DOC_MANAGER._get("project_name") or ""

def set_project_name(project_name):
    return PROJECT_DOC_MANAGER._save({"project_name": project_name})