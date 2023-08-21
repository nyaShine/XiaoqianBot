from botpy.forum import OpenThread


async def open_forum_thread_create_handler(client, open_forum_thread: OpenThread):
    # attributes = {attr: str(getattr(open_forum_thread, attr)) for attr in open_forum_thread.__slots__
    #               if not attr.startswith('_') and hasattr(open_forum_thread, attr)}
    # print(attributes)
    pass
