
import os
import traceback
import logging
import inspect
from logging.handlers import TimedRotatingFileHandler
from threading import RLock


class LoggerFactory(object):
    TYPE = "FILE"
    LOG_FORMAT = "[%(levelname)s] [%(asctime)s] [%(module)s.%(funcName)s] [line:%(lineno)d]: %(message)s"
    logging.basicConfig(format=LOG_FORMAT)
    LEVEL = logging.DEBUG
    logger_dict = {}
    global_handler_dict = {}

    LOG_DIR = None
    PARENT_LOG_DIR = None
    log_share = True

    append_to_parent_log = None

    lock = RLock()
    # CRITICAL = 50
    # FATAL = CRITICAL
    # ERROR = 40
    # WARNING = 30
    # WARN = WARNING
    # INFO = 20
    # DEBUG = 10
    # NOTSET = 0
    levels = (10, 20, 30, 40)
    schedule_logger_dict = {}

    @staticmethod
    def set_directory(directory=None, parent_log_dir=None,
                      append_to_parent_log=None, force=False):
        if parent_log_dir:
            LoggerFactory.PARENT_LOG_DIR = parent_log_dir
        if append_to_parent_log:
            LoggerFactory.append_to_parent_log = append_to_parent_log
        with LoggerFactory.lock:
            if not directory:
                directory = get_project_base_directory("logs")
            if not LoggerFactory.LOG_DIR or force:
                LoggerFactory.LOG_DIR = directory
            if LoggerFactory.log_share:
                oldmask = os.umask(000)
                os.makedirs(LoggerFactory.LOG_DIR, exist_ok=True)
                os.umask(oldmask)
            else:
                os.makedirs(LoggerFactory.LOG_DIR, exist_ok=True)
            for loggerName, ghandler in LoggerFactory.global_handler_dict.items():
                for className, (logger,
                                handler) in LoggerFactory.logger_dict.items():
                    logger.removeHandler(ghandler)
                ghandler.close()
            LoggerFactory.global_handler_dict = {}
            for className, (logger,
                            handler) in LoggerFactory.logger_dict.items():
                logger.removeHandler(handler)
                _handler = None
                if handler:
                    handler.close()
                if className != "default":
                    _handler = LoggerFactory.get_handler(className)
                    logger.addHandler(_handler)
                LoggerFactory.assemble_global_handler(logger)
                LoggerFactory.logger_dict[className] = logger, _handler

    @staticmethod
    def new_logger(name):
        logger = logging.getLogger(name)
        logger.propagate = False
        logger.setLevel(LoggerFactory.LEVEL)
        return logger

    @staticmethod
    def get_logger(class_name=None):
        with LoggerFactory.lock:
            if class_name in LoggerFactory.logger_dict.keys():
                logger, handler = LoggerFactory.logger_dict[class_name]
                if not logger:
                    logger, handler = LoggerFactory.init_logger(class_name)
            else:
                logger, handler = LoggerFactory.init_logger(class_name)
            return logger

    @staticmethod
    def get_global_handler(logger_name, level=None, log_dir=None):
        if not LoggerFactory.LOG_DIR:
            return logging.StreamHandler()
        if log_dir:
            logger_name_key = logger_name + "_" + log_dir
        else:
            logger_name_key = logger_name + "_" + LoggerFactory.LOG_DIR
        # if loggerName not in LoggerFactory.globalHandlerDict:
        if logger_name_key not in LoggerFactory.global_handler_dict:
            with LoggerFactory.lock:
                if logger_name_key not in LoggerFactory.global_handler_dict:
                    handler = LoggerFactory.get_handler(
                        logger_name, level, log_dir)
                    LoggerFactory.global_handler_dict[logger_name_key] = handler
        return LoggerFactory.global_handler_dict[logger_name_key]

    @staticmethod
    def get_handler(class_name, level=None, log_dir=None,
                    log_type=None, job_id=None):
        if not log_type:
            if not LoggerFactory.LOG_DIR or not class_name:
                return logging.StreamHandler()
                # return Diy_StreamHandler()

            if not log_dir:
                log_file = os.path.join(
                    LoggerFactory.LOG_DIR,
                    "{}.log".format(class_name))
            else:
                log_file = os.path.join(log_dir, "{}.log".format(class_name))
        else:
            log_file = os.path.join(log_dir, "rag_flow_{}.log".format(
                log_type) if level == LoggerFactory.LEVEL else 'rag_flow_{}_error.log'.format(log_type))

        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        if LoggerFactory.log_share:
            handler = ROpenHandler(log_file,
                                   when='D',
                                   interval=1,
                                   backupCount=14,
                                   delay=True)
        else:
            handler = TimedRotatingFileHandler(log_file,
                                               when='D',
                                               interval=1,
                                               backupCount=14,
                                               delay=True)
        if level:
            handler.level = level

        return handler

    @staticmethod
    def init_logger(class_name):
        with LoggerFactory.lock:
            logger = LoggerFactory.new_logger(class_name)
            handler = None
            if class_name:
                handler = LoggerFactory.get_handler(class_name)
                logger.addHandler(handler)
                LoggerFactory.logger_dict[class_name] = logger, handler

            else:
                LoggerFactory.logger_dict["default"] = logger, handler

            LoggerFactory.assemble_global_handler(logger)
            return logger, handler

    @staticmethod
    def assemble_global_handler(logger):
        if LoggerFactory.LOG_DIR:
            for level in LoggerFactory.levels:
                if level >= LoggerFactory.LEVEL:
                    level_logger_name = logging._levelToName[level]
                    logger.addHandler(
                        LoggerFactory.get_global_handler(
                            level_logger_name, level))
        if LoggerFactory.append_to_parent_log and LoggerFactory.PARENT_LOG_DIR:
            for level in LoggerFactory.levels:
                if level >= LoggerFactory.LEVEL:
                    level_logger_name = logging._levelToName[level]
                    logger.addHandler(
                        LoggerFactory.get_global_handler(level_logger_name, level, LoggerFactory.PARENT_LOG_DIR))



class ROpenHandler(TimedRotatingFileHandler):
    def _open(self):
        prevumask = os.umask(000)
        rtv = TimedRotatingFileHandler._open(self)
        os.umask(prevumask)
        return rtv

def get_project_base_directory(*args):
    global PROJECT_BASE
    if PROJECT_BASE is None:
        PROJECT_BASE = os.path.abspath(
            os.path.join(
                os.path.dirname(os.path.realpath(__file__)),
                os.pardir,
                os.pardir,
            )
        )

    if args:
        return os.path.join(PROJECT_BASE, *args)
    return PROJECT_BASE


def setDirectory(directory=None):
    LoggerFactory.set_directory(directory)


def setLevel(level):
    LoggerFactory.LEVEL = level


def getLogger(className=None, useLevelFile=False):
    if className is None:
        frame = inspect.stack()[1]
        module = inspect.getmodule(frame[0])
        className = 'stat'
    return LoggerFactory.get_logger(className)


def exception_to_trace_string(ex):
    return "".join(traceback.TracebackException.from_exception(ex).format())
