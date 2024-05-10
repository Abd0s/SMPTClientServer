import logging

def setup_logger() -> None:

    # create logger
    logger: logging.Logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    # create console handler and set level to debug
    console_handler: logging.StreamHandler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)

    # create formatter
    formatter: logging.Formatter = logging.Formatter("%(asctime)-24s %(threadName)-16s %(levelname)-8s %(message)s")

    # add formatter to ch
    console_handler.setFormatter(formatter)

    # add ch to logger
    logger.addHandler(console_handler) 
