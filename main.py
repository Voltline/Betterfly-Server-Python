import Utils.Server
import logging
path = "./Config/config.json"

if __name__ == '__main__':
    while True:
        try:
            server = Utils.Server.EpollChatServer(path);
            server.run()
        except KeyboardInterrupt as e:
            server.shutdown()
            logging.info(f"Server Closed", exc_info=True)
            break
        except Exception as e:
            logging.error(f"Unhandled exception in main: {e}", exc_info=True)