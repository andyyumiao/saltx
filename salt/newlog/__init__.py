import logging


masterLogger = logging.getLogger('masterXLogger')
masterLogger.setLevel(logging.INFO)
fh = logging.FileHandler('/var/log/salt/xmaster.log', encoding='utf-8')
fh.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
masterLogger.addHandler(fh)