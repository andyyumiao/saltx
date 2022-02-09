# -*- coding: utf-8 -*-

import re
import uuid
import time
#import redis
import traceback
import os
import signal
import logging
import errno
import subprocess
import json
import sys
import multiprocessing
import logging
import collections

import gevent
from gevent.pool import Pool
from gevent import monkey
monkey.patch_all(thread=False)

# Import 3rd-party libs
import salt.ext.six as six
from salt.utils import parsers, print_cli
from salt.client import get_local_client
from redis.sentinel import Sentinel
import sys
reload(sys)
sys.setdefaultencoding("utf-8")

from salt.exceptions import (
        SaltClientError,
        SaltInvocationError,
        EauthAuthenticationError
        )

from salt.selflog.manual_log import ManualLog

# Imports related to websocket

maid_log = ManualLog().get_logger('salt_maid_module')

# NOTE: Message Type Enum
# work: normal working message type
# ping: ping/pang message type
# interrupt: the mesage type for interrupt with something issue, e.g. error or biz check
class MessageType:
    WORK = 'work'
    PING = 'ping'
    INTERRUPT = 'interrupt'

class FunctionType:
    SYNC_RUN = 'sync_run'
    ASYNC_RUN = 'aysnc_run'
    LOOKUP_JID = 'jobs.list_job'
    LIST_JOBS = 'jobs.list_jobs'
    FIND_ACCEPT = 'find_accept'
    SALT_CP = 'salt_cp'

class TopicType:
    JOBS = 'jobs_'

class SaltStaticConstants:
    API_USER = 'salt-tool'
    API_PWD = 'salt-tool123'
    API_EAUTH = 'pam'

class Base(parsers.SaltCMDOptionParser):
    def __init__(self, **config):
        try:
            redisIpConf = config['_channel_redis_sentinel']
            if not redisIpConf:
                log.error('Can not find valid ip config.')
            else:
                redisConfigure = []
                redisIpSplit = redisIpConf.split(',')
                for redisInfo in redisIpSplit:
                    redisInfoSplit = redisInfo.split(':')
                    redisConfigure.append((redisInfoSplit[0], redisInfoSplit[1]))

                self.sentinel = Sentinel(redisConfigure)
                self.redisInstance = self.sentinel.master_for('redis-master', password=config['_channel_redis_password'])

                ##self._pool = redis.ConnectionPool(host=config['_channel_redis_host'], port=config['_channel_redis_port'], db=1, password=config['_channel_redis_password'])
                ##self.redisInstance = redis.StrictRedis(connection_pool=self._pool)
                self._master_pub_topic = config['_master_pub_topic']
                self._none_match_ip = 'no_ip_matched'
                self._sub_node = config['_sub_node']

        except:
            #log.error("redis init failed.")
            log.error(traceback.format_exc())
            #print_cli("redis实例化失败.")

    def clearProcess(self):
        os.kill(os.getpid(), signal.SIGKILL)
        os.killpg(os.getpgid(os.getpid()), signal.SIGKILL)

    def executeSaltCmd(self, cmd, msg_in=''):
        try:
            proc = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,)
            stdout_value, stderr_value = proc.communicate(msg_in)

            return stdout_value, stderr_value
        except Exception, e:
            log.error(traceback.format_exc())
            #print('traceback.format_exc():\n%s' % traceback.format_exc())

    def getAcceptIp(self):
        #stdout_val, stderr_val = self.executeSaltCmd("salt-key -l acc")

        stdout_val, stderr_val = self.executeSaltCmd("salt-key -l acc|grep -v Keys")

        syndicList = stdout_val.splitlines()
        if syndicList == "":
           return ""
        #syndicList = re.findall(
        #    r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b", stdout_val, re.M)
        return syndicList


class MasterPub(Base):
    def __init__(self, **config):
        super(MasterPub, self).__init__(**config)

    # def __init__(self):
    #     Process.__init__(self)

    # def run(self):
    #     self.handleListenback()

    def pullAccept(self):
        return self.getAcceptIp()
        #self.syndic_count = len(syndicList)

    def publishToSyndicSub(self, message):
        self.redisInstance.publish(self._master_pub_topic, message)

    def getRedisInstance(self):
        return self.redisInstance

    def getReadyBackupMaid(self):
        return self.redisInstance.smembers('backup_maid')


class SyndicSubcribe(Base):
    def __init__(self, **config):
        super(SyndicSubcribe, self).__init__(**config)

    def exec_lowstate(self, client=None, token=None, lowstate=None, opts=None):
        '''
        Pull a Low State data structure from request and execute the low-data
        chunks through Salt. The low-data chunks will be updated to include the
        authorization token for the current session.
        '''
        # Make any requested additions or modifications to each lowstate, then
        # execute each one and yield the result.
        for chunk in lowstate:
            if token:
                chunk['token'] = token
                chunk['__current_eauth_user'] = SaltStaticConstants.API_USER
                chunk['__current_eauth_groups'] = [SaltStaticConstants.API_USER]

            if 'token' in chunk:
                # Make sure that auth token is hex
                try:
                    int(chunk['token'], 16)
                except (TypeError, ValueError):
                    print(raceback.format_exc())

            if client:
                chunk['client'] = client

            # Make any 'arg' params a list if not already.
            # This is largely to fix a deficiency in the urlencoded format.
            if 'arg' in chunk and not isinstance(chunk['arg'], list):
                chunk['arg'] = [chunk['arg']]

            import salt.netapi
            self.api = salt.netapi.NetapiClient(opts)
            ret = self.api.run(chunk)

            # Sometimes Salt gives us a return and sometimes an iterator
            if isinstance(ret, collections.Iterator):
                for i in ret:
                    yield i
            else:
                yield ret

    def run(self, wrapMessage, subNode, opts):
        try:
            self.local_client = get_local_client(
                auto_reconnect=True)
        except SaltClientError as exc:
            self.exit(2, '{0}\n'.format(exc))
            return

        error = None

        if 'type' in wrapMessage:
            if wrapMessage['type'] == FunctionType.SALT_CP:
                kwargs = wrapMessage['kwargs']

                # check if contains the ip list
                # the final wait for execute ip list
                fntgt = []
                tgt_type = 'glob'
                if isinstance(kwargs['tgt'], list):
                    tgt_type = 'list'
                    localAcceptIpList = self.getAcceptIp()
                    fntgt = [ip for ip in kwargs['tgt'] if ip in localAcceptIpList]
                    if len(fntgt) == 0:
                        self.redisInstance.publish(wrapMessage['tempTopic'], json.dumps(
                            {'type': MessageType.INTERRUPT, 'message': 'Can not find any matched ip.',
                             'sub_ip': subNode}, ensure_ascii=False, encoding='utf-8'))
                        return
                    else:
                        kwargs['tgt'] = fntgt
                else:
                    if kwargs['tgt'] == '*':
                        pass
                    else:
                        if not is_valid_ip(kwargs['tgt']):
                            self.redisInstance.publish(wrapMessage['tempTopic'], json.dumps(
                                {'type': MessageType.INTERRUPT, 'message': 'Find invalid ip: %s' % kwargs['tgt'],
                                 'sub_ip': subNode}, ensure_ascii=False, encoding='utf-8'))
                            return

                cp_arg = wrapMessage['cp_arg']
                args = [kwargs['tgt'],
                        'cp.recv',
                        cp_arg,
                        opts['timeout'],
                        ]

                args = byteify(args)
                args.append(tgt_type)
                print('args: %s' % args)

                cp_result = self.local_client.cmd(*args)
                print('cp_result: %s' % cp_result)

                self.redisInstance.publish(wrapMessage['tempTopic'],
                                           json.dumps({'cp_result': cp_result, 'dataType': 'SALT_CP'},
                                                      ensure_ascii=False, encoding='utf-8'))
                self.redisInstance.publish(wrapMessage['tempTopic'],
                                           json.dumps({'type': MessageType.WORK, 'result': True, 'sub_ip': subNode},
                                                      ensure_ascii=False, encoding='utf-8'))
            elif wrapMessage['type'] == FunctionType.FIND_ACCEPT:
                localAcceptIpList = self.getAcceptIp()
                self.redisInstance.publish(wrapMessage['tempTopic'], json.dumps({'ip_list': localAcceptIpList, 'dataType': 'ACCEPT_MINION'}, ensure_ascii=False, encoding='utf-8'))
                self.redisInstance.publish(wrapMessage['tempTopic'],
                                           json.dumps({'type': MessageType.WORK, 'result': True, 'sub_ip': subNode},
                                                      ensure_ascii=False, encoding='utf-8'))
            elif wrapMessage['type'] == FunctionType.SYNC_RUN:
                kwargs = wrapMessage['kwargs']
                #check if contains the ip list
                #the final wait for execute ip list
                fntgt = []
                if isinstance(kwargs['tgt'], list):
                    localAcceptIpList = self.getAcceptIp()
                    fntgt = [ip for ip in kwargs['tgt'] if ip in localAcceptIpList]
                    if len(fntgt) == 0:
                        self.redisInstance.publish(wrapMessage['tempTopic'], json.dumps({'type': MessageType.INTERRUPT, 'message': 'Can not find any matched ip.', 'sub_ip': subNode}, ensure_ascii=False, encoding='utf-8'))
                        return
                    else:
                        kwargs['tgt'] = fntgt
                else:
                    if kwargs['tgt'] == '*':
                        pass
                    else:
                        if not is_valid_ip(kwargs['tgt']):
                            self.redisInstance.publish(wrapMessage['tempTopic'], json.dumps({'type': MessageType.INTERRUPT, 'message': 'Find invalid ip: %s' % kwargs['tgt'], 'sub_ip': subNode}, ensure_ascii=False, encoding='utf-8'))
                            return

                cmd_func = self.local_client.cmd_cli

                maid_log.info('for loop kwargs: %s' % kwargs)
                for full_ret in cmd_func(**kwargs):
                    try:
                        import salt.cli.salt
                        client = salt.cli.salt.SaltCMD()
                        ret_, out, retcode = client._format_ret(full_ret)
                        self.redisInstance.publish(wrapMessage['tempTopic'], json.dumps({'ret_': ret_, 'out': out, 'retcode': retcode}, ensure_ascii=False, encoding='utf-8'))
                    except Exception, e:
                        maid_log.info('traceback.format_exc():\n%s' % traceback.format_exc())


                self.redisInstance.publish(wrapMessage['tempTopic'], json.dumps({'type': MessageType.WORK, 'result': True, 'sub_ip': subNode}, ensure_ascii=False, encoding='utf-8'))
                maid_log.info('end for loop: %s' % json.dumps({'type': MessageType.WORK, 'result': True, 'error': error, 'sub_ip': subNode}, ensure_ascii=False, encoding='utf-8'))
            elif wrapMessage['type'] == FunctionType.ASYNC_RUN:
                kwargs = wrapMessage['kwargs']

                # check if contains the ip list
                # the final wait for execute ip list
                fntgt = []
                if isinstance(kwargs['tgt'], list):
                    localAcceptIpList = self.getAcceptIp()
                    fntgt = [ip for ip in kwargs['tgt'] if ip in localAcceptIpList]
                    if len(fntgt) == 0:
                        self.redisInstance.publish(wrapMessage['tempTopic'], json.dumps(
                            {'type': MessageType.INTERRUPT, 'message': 'Can not find any matched ip.',
                             'sub_ip': subNode}, ensure_ascii=False, encoding='utf-8'))
                        return
                    else:
                        kwargs['tgt'] = fntgt
                else:
                    if kwargs['tgt'] == '*':
                        pass
                    else:
                        if not is_valid_ip(kwargs['tgt']):
                            self.redisInstance.publish(wrapMessage['tempTopic'], json.dumps(
                                {'type': MessageType.INTERRUPT, 'message': 'Find invalid ip: %s' % kwargs['tgt'],
                                 'sub_ip': subNode}, ensure_ascii=False, encoding='utf-8'))
                            return

                jid = self.local_client.cmd_async(**kwargs)
                maid_log.info('Executed command with job ID: {0}'.format(jid))
                # NOTE: just save jid mapping 24h
                self.redisInstance.sadd(wrapMessage['jid'], jid)
                self.redisInstance.expire(wrapMessage['jid'], 86400)
                
                maid_log.info('Latest jid change for: {0}'.format(jid))
                # self.redisInstance.set('p_s_job_{0}'.format(jid), wrapMessage['jid'])
                # self.redisInstance.expire('p_s_job_{0}'.format(jid), 86400)

                # subCacheKey = 'jobs_subcache_{0}_{1}'.format(wrapMessage['jid'], subNode)
                # maid_log.info('Handle subCacheKey: {0}, {1}'.format(subCacheKey, jid))
                # self.redisInstance.set(subCacheKey, jid)
                # self.redisInstance.expire(subCacheKey, 86400)

                self.redisInstance.publish(wrapMessage['tempTopic'], json.dumps({'type': MessageType.WORK, 'result': True, 'error': error, 'sub_ip': subNode}, ensure_ascii=False, encoding='utf-8'))
                return
            elif wrapMessage['type'] == FunctionType.LOOKUP_JID:
                kwargs = wrapMessage['kwargs']
                maid_log.info('Lookup job ID: {0}'.format(kwargs['jid']))

                subCacheKey = 'jobs_subcache_{0}_{1}'.format(kwargs['jid'], subNode)
                subCacheValue = self.redisInstance.get(subCacheKey)
                maid_log.info('-------newrun-------subCacheValue-----------: %s' % subCacheValue)
                if subCacheValue:
                    import salt.config
                    __opts__ = salt.config.client_config(
                        os.environ.get('SALT_MASTER_CONFIG', '/etc/salt/master'))

                    creds = {'username': SaltStaticConstants.API_USER, 'password': SaltStaticConstants.API_PWD, 'eauth': SaltStaticConstants.API_EAUTH}
                    import salt.auth
                    self.auth = salt.auth.Resolver(__opts__)
                    tokenObj = self.auth.mk_token(creds)
                    maid_log.info('-------newrun-------tokenObj3-----------: %s' % tokenObj)

                    lowstate = {'client': 'runner'}
                    lowstate.update({'fun': 'jobs.list_job', 'jid': subCacheValue})

                    lowstate = [lowstate]
                    job_ret_info = list(self.exec_lowstate(
                        token=tokenObj['token'], lowstate=lowstate, opts=__opts__))
                    maid_log.info('-------newrun-------job_ret_info-----------: %s' % job_ret_info)

                    self.redisInstance.publish(wrapMessage['tempTopic'], json.dumps({'jobrets': job_ret_info}, ensure_ascii=False, encoding='utf-8'))

                self.redisInstance.publish(wrapMessage['tempTopic'], json.dumps({'type': MessageType.WORK, 'result': True, 'error': error, 'sub_ip': subNode}, ensure_ascii=False, encoding='utf-8'))
                return
            elif wrapMessage['type'] == FunctionType.LIST_JOBS:
                kwargs = wrapMessage['kwargs']

                import salt.config
                __opts__ = salt.config.client_config(
                    os.environ.get('SALT_MASTER_CONFIG', '/etc/salt/master'))

                creds = {'username': SaltStaticConstants.API_USER, 'password': SaltStaticConstants.API_PWD, 'eauth': SaltStaticConstants.API_EAUTH}
                self.auth = salt.auth.Resolver(__opts__)
                tokenObj = self.auth.mk_token(creds)
                print('-------newrun-------tokenObj-----------: %s' % tokenObj)

                lowstate = {'client': 'runner'}
                lowstate.update({'fun': 'jobs.list_jobs'})

                lowstate = [lowstate]
                job_ret_info = list(self.exec_lowstate(
                    token=tokenObj['token'], lowstate=lowstate, opts=__opts__))
                print('-------newrun-------list_jobs-----------: %s' % job_ret_info)

                self.redisInstance.publish(wrapMessage['tempTopic'], json.dumps({'jobrets': job_ret_info}, ensure_ascii=False, encoding='utf-8'))

                self.redisInstance.publish(wrapMessage['tempTopic'], json.dumps({'type': MessageType.WORK, 'result': True, 'error': error, 'sub_ip': subNode}, ensure_ascii=False, encoding='utf-8'))
                return
            else:
                self.redisInstance.publish(wrapMessage['tempTopic'], json.dumps({'type': MessageType.INTERRUPT, 'message': 'Unvalid function type: {0}'.format(wrapMessage['type']), 'sub_ip': subNode}, ensure_ascii=False, encoding='utf-8'))
                return


    def startListen(self, opts):
        try:
            subNode = opts['id']
            from salt.newrun import (json, byteify, MessageType)

            redischannel_sub = self.redisInstance.pubsub()
            redischannel_sub.subscribe(self._master_pub_topic.split(','))

            pool = Pool(20000)
            for message in redischannel_sub.listen():
                try:
                    messageType = byteify(message)
                    if messageType['type'] == 'message':
                        maid_log.info("received master data: %s" % messageType['data'])

                        wrapMesage = json.loads(messageType['data'])
                        self.redisInstance.publish(wrapMesage['tempTopic'], json.dumps({'type': MessageType.PING, 'sub_ip': subNode}, ensure_ascii=False, encoding='utf-8'))

                        ##fork sub process to handle the task
                        maid_log.info("fork process for: " % wrapMesage)
                        # p = multiprocessing.Process(target=self.run, args=(wrapMesage, subNode, opts))
                        # p.start()
                        g = pool.spawn(self.run, wrapMesage, subNode, opts)
                        #g.join()
                        g.start()

                except Exception, e:
                    maid_log.info(traceback.format_exc())
                    #print('traceback.format_exc():\n%s' % traceback.format_exc())

        except Exception, e:
            maid_log.info(traceback.format_exc())
            #print('traceback.format_exc():\n%s' % traceback.format_exc())


def is_valid_ip(ip):
    m = re.match(r"^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$", ip)
    return bool(m) and all(map(lambda n: 0 <= int(n) <= 255, m.groups()))

# NOTE: switch json object based on ascii to utf-8
def byteify(input, encoding='utf-8'):
    if isinstance(input, dict):
        return {byteify(key): byteify(value) for key, value in input.iteritems()}
    elif isinstance(input, list):
        return [byteify(element) for element in input]
    elif isinstance(input, unicode):
        return input.encode(encoding)
    else:
        return input
