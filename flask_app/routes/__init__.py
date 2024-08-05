def init_api(api):
    from .graph import api as graph_ns
    from .upload import api as upload_ns
    from .quiz import api as quiz_ns
    from .health import api as health_ns
    from .summary import api as summary_ns
    from .test import api as test_ns
    from .note import api as note_ns
    from .course import api as course_ns
    from .user import api as user_ns
    from .auth import api as auth_ns

    api.add_namespace(graph_ns)
    api.add_namespace(upload_ns)
    api.add_namespace(quiz_ns)
    api.add_namespace(health_ns)
    api.add_namespace(summary_ns)
    api.add_namespace(test_ns)
    api.add_namespace(note_ns)
    api.add_namespace(course_ns)
    api.add_namespace(user_ns)
    api.add_namespace(auth_ns)