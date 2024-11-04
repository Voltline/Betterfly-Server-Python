import Utils.Server
from Utils.color_logger import get_logger
path = "./Config/config.json"
logger = get_logger(__name__)

if __name__ == '__main__':
    while True:
        try:
            server = Utils.Server.EpollChatServer(path)
            server.run()
        except KeyboardInterrupt as e:
            server.shutdown()
            logger.info(f"Server Closed", exc_info=True)
            break
        except Exception as e:
            logger.error(f"Unhandled exception in main: {e}", exc_info=True)
