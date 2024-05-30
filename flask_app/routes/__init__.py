
def init_api(api):
    from .whisper import api as whisper_ns

    api.add_namespace(whisper_ns)