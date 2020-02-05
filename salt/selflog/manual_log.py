#!/usr/bin/env python
# _*_ coding: utf-8 _*_
import commands
import json
import sys
import traceback

__author__ = 'hua.xiao'

import logging.config
import os

# sys.path.append('/var/cache/salt/minion/extmods/modules/log')
# import log_cfg

# 日志配置
log_cfg = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "DEBUG",
            "formatter": "simple",
            "stream": "ext://sys.stdout"
        },
        "salt_api_file_handler": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "DEBUG",
            "formatter": "simple",
            "filename": "/tmp/salt/api/info.log",
            "maxBytes": 104857600,
            "backupCount": 20,
            "encoding": "utf8"
        },
        "salt_redis_file_handler": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "DEBUG",
            "formatter": "simple",
            "filename": "/tmp/salt/redis/info.log",
            "maxBytes": 104857600,
            "backupCount": 20,
            "encoding": "utf8"
        },
        "salt_main_file_handler": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "DEBUG",
            "formatter": "simple",
            "filename": "/tmp/salt/main/info.log",
            "maxBytes": 104857600,
            "backupCount": 20,
            "encoding": "utf8"
        },
        "salt_maid_file_handler": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "DEBUG",
            "formatter": "simple",
            "filename": "/tmp/salt/maid/info.log",
            "maxBytes": 104857600,
            "backupCount": 20,
            "encoding": "utf8"
        },
    },
    "loggers": {
        "salt_api_module": {
            "level": "INFO",
            "handlers": [
                "console",
                "salt_api_file_handler"
            ],
            "propagate": "no"
        },
        "salt_redis_module": {
            "level": "INFO",
            "handlers": [
                "salt_redis_file_handler"
            ],
            "propagate": "no"
        },
        "salt_main_module": {
            "level": "INFO",
            "handlers": [
                "salt_main_file_handler"
            ],
            "propagate": "no"
        },
        "salt_maid_module": {
            "level": "INFO",
            "handlers": [
                "salt_maid_file_handler"
            ],
            "propagate": "no"
        }
    }
}


class ManualLog(object):

    def __init__(self):
        if log_cfg:
            # 检查&创建目录
            self.check_and_create_logdir(log_cfg['handlers']['salt_api_file_handler']['filename'])
            self.check_and_create_logdir(log_cfg['handlers']['salt_redis_file_handler']['filename'])
            self.check_and_create_logdir(log_cfg['handlers']['salt_main_file_handler']['filename'])
            self.check_and_create_logdir(log_cfg['handlers']['salt_maid_file_handler']['filename'])
            # self.check_and_create_logdir(log_cfg['handlers']['dn_update_info_file_handler']['filename'])
            logging.config.dictConfig(log_cfg)
        else:
            logging.basicConfig(level=logging.DEBUG)

    def check_and_create_logdir(self, file_name):
        try:
            if file_name is not None and file_name != '':
                log_path = os.sep.join(file_name.split(os.sep)[:-1])
                if not os.path.exists(log_path):
                    os.makedirs(log_path)
        except:
            print('traceback.format_exc():\n%s' % traceback.format_exc())

    def get_logger(self, log_name):
        my_log = logging.getLogger(log_name)
        return my_log

    def get_current_path(self, cfg_file):
        runcommand = "find / -name '%s'" % cfg_file
        (status, output) = commands.getstatusoutput(runcommand)
        if status == 0 and output:
            ret = output.split('\n')[0]
            return ret
            # os.sep.join(ret.split(os.sep)[:-1])
        return cfg_file


if __name__ == '__main__':
    my_salt_log = ManualLog().get_logger('master_monitor_info')
    my_salt_log.info("master aaaaa")
