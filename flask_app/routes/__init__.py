
def init_api(api):
    from .whisper import api as whisper_ns
    from .graph import api as graph_ns

    api.add_namespace(graph_ns)
    api.add_namespace(whisper_ns)