# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import, print_function
import sys

sys.modules['pkg_resources'] = None
import os

# Import Salt libs
from salt.ext.six import string_types
from salt.utils import parsers, print_cli
from salt.utils.args import yamlify_arg
from salt.utils.verify import verify_log
from salt.exceptions import (
    SaltClientError,
    SaltInvocationError,
    EauthAuthenticationError
)

# Import 3rd-party libs
import salt.ext.six as six
import traceback
import signal
import time
import threading
from salt.selflog.manual_log import ManualLog

# Imports related to websocket

main_log = ManualLog().get_logger('salt_main_module')

class SaltCMD(parsers.SaltCMDOptionParser):

    def quit(self, signum, frame):
        try:
            os._exit(0)
        except:
            print('Killed saltx with ctrl+c')

    ###for salt router
    def salt_router(self):
        '''
        Execute the salt command line
        '''
        # import salt.client
        self.parse_args()
        if self.config['order_masters'] == True:
            self.new_run()
        else:
            self.run()

    ###for saltx router
    def saltx_router(self):
        '''
        Execute the salt command line
        '''
        # import salt.client
        self.parse_args()

        self.run()

    def new_run(self):
        # '''
        # Execute the salt command line
        # '''
        import salt.client
        # self.parse_args()

        # print('################:%s' % (self.config['order_masters']==True))
        signal.signal(signal.SIGINT, self.quit)
        signal.signal(signal.SIGTERM, self.quit)

        if self.config['log_level'] not in ('quiet',):
            # Setup file logging!
            self.setup_logfile_logger()
            verify_log(self.config)

        try:
            # We don't need to bail on config file permission errors
            # if the CLI process is run with the -a flag
            skip_perm_errors = self.options.eauth != ''

            self.local_client = salt.client.get_local_client(
                self.get_config_file_path(),
                skip_perm_errors=skip_perm_errors,
                auto_reconnect=True)
        except SaltClientError as exc:
            self.exit(2, '{0}\n'.format(exc))
            return

        if self.options.preview_target:
            minion_list = self._preview_target()
            self._output_ret(minion_list, self.config.get('output', 'nested'))
            return

        if self.options.timeout <= 0:
            self.options.timeout = self.local_client.opts['timeout']

        # read tgt list from file
        if self.options.file_target:
            try:
                with open(self.config['tgt']) as xf:
                    xfContent = xf.read().strip("\n").strip(' ')
                    if xfContent == '':
                        self.exit(2, 'Find empty ip list from {0}, pls check.\n'.format(self.config['tgt']))
                        return
                    if ',' in xfContent:
                        self.config['tgt'] = xfContent.split(",")
                        self.selected_target_option = 'list'
                    elif '\n' in xfContent:
                        self.config['tgt'] = xfContent.split("\n")
                        self.selected_target_option = 'list'
                    else:
                        print('Find invalid args with -X.')
                        return
            except IOError as exc:
                self.exit(2, '{0}\n'.format(exc))
                return

        kwargs = {
            'tgt': self.config['tgt'],
            'fun': self.config['fun'],
            'arg': self.config['arg'],
            'timeout': self.options.timeout,
            'show_timeout': self.options.show_timeout,
            'show_jid': self.options.show_jid}

        # kwargs = self.config
        # kwargs['timeout'] = self.options.timeout
        # kwargs['show_timeout'] = self.options.show_timeout
        # kwargs['show_jid'] = self.options.show_jid

        kwargs['delimiter'] = self.options.delimiter
        if self.selected_target_option:
            kwargs['tgt_type'] = self.selected_target_option
        else:
            kwargs['tgt_type'] = 'glob'

        if getattr(self.options, 'return'):
            kwargs['ret'] = getattr(self.options, 'return')

        if getattr(self.options, 'return_config'):
            kwargs['ret_config'] = getattr(self.options, 'return_config')

        if getattr(self.options, 'return_kwargs'):
            kwargs['ret_kwargs'] = yamlify_arg(
                getattr(self.options, 'return_kwargs'))

        if getattr(self.options, 'module_executors'):
            kwargs['module_executors'] = yamlify_arg(getattr(self.options, 'module_executors'))

        if getattr(self.options, 'metadata'):
            kwargs['metadata'] = yamlify_arg(
                getattr(self.options, 'metadata'))

        # If using eauth and a token hasn't already been loaded into
        # kwargs, prompt the user to enter auth credentials
        if 'token' not in kwargs and 'key' not in kwargs and self.options.eauth:
            # This is expensive. Don't do it unless we need to.
            import salt.auth
            resolver = salt.auth.Resolver(self.config)
            res = resolver.cli(self.options.eauth)
            if self.options.mktoken and res:
                tok = resolver.token_cli(
                    self.options.eauth,
                    res
                )
                if tok:
                    kwargs['token'] = tok.get('token', '')
            if not res:
                sys.stderr.write('ERROR: Authentication failed\n')
                sys.exit(2)
            kwargs.update(res)
            kwargs['eauth'] = self.options.eauth

        self.newopt = self.config
        sub_timeout = self.newopt['channel_sub_timeout']
        if self.options.timeout > sub_timeout:
            sub_timeout = self.options.timeout

        self.bootConfig = {'_sub_timeout': sub_timeout, '_sub_node': '',
                           '_channel_redis_sentinel': self.newopt['channel_redis_sentinel'],
                           '_channel_redis_password': self.newopt['channel_redis_password'],
                           '_master_pub_topic': self.newopt['id']}

        # NOTE: Only in super master, filter no-response ip, when use saltx
        def getPassedIp():
            import numpy
            numpy.warnings.filterwarnings('ignore')
            passed_ip = numpy.loadtxt('/data0/md/ip.md', dtype=numpy.str)
            return passed_ip

        missedList = set()

        runAllminion = False

        if isinstance(kwargs['tgt'], list):
            passed_ip = getPassedIp()
            kwargs['tgt'] = [i for i in kwargs['tgt'] if i not in passed_ip]
            if len(kwargs['tgt']) == 0:
                print_cli('There are nothing iplist to be apply.')
                return
        else:
            if kwargs['tgt'] != '*':
                passed_ip = getPassedIp()
                if kwargs['tgt'] in passed_ip:
                    print_cli('There are nothing iplist to be apply.')
                    return
            else:
                runAllminion = True
        import salt.newrun

        clientPub = salt.newrun.MasterPub(**self.bootConfig)
        if self.config['async']:
            # NOTE: generate a jid for saltx
            jid = salt.utils.jid.gen_jid()

            wrapMesage = {'type': salt.newrun.FunctionType.ASYNC_RUN, 'jid': jid, 'kwargs': kwargs,
                          'tempTopic': str(salt.newrun.uuid.uuid1())}

            clientPub.publishToSyndicSub(salt.newrun.json.dumps(wrapMesage))

            print_cli('Executed command with master job ID: {0}'.format(jid))
            return
        else:
            wrapMesage = {'type': salt.newrun.FunctionType.SYNC_RUN, 'kwargs': kwargs,
                          'tempTopic': str(salt.newrun.uuid.uuid1())}

            batch_hold = 0

            lossSyndic = []
            repeatet = set()
            emptyRet = []
            noResponseRet = []
            noConnectRet = []
            # running, make sure to be batch count
            global batch_running
            batch_running = set()
            # init batch ip
            batch_init = set()
            comeSubList = clientPub.pullAccept()
            resultPingSet = []
            resultExeSet = []
            global normalsize
            normalsize = 0
            sucset = set()

            debugSet = set()

            def batchExecuteCallback(selfIp, clientPub, redisChannel):
                while len(batch_running) <= 0:
                    tmpKwargs = wrapMesage['kwargs']
                    try:
                        for i in range(batch_hold):
                            batch_running.add(batch_init.pop())

                        # trigger to sub run
                        tmpKwargs['tgt'] = list(batch_running)
                        wrapMesage['kwargs'] = tmpKwargs
                        batchRun(wrapMesage, selfIp, clientPub, redisChannel)
                    except:
                        if len(batch_running) > 0:
                            # trigger to sub run
                            tmpKwargs['tgt'] = list(batch_running)
                            wrapMesage['kwargs'] = tmpKwargs
                            batchRun(wrapMesage, selfIp, clientPub, redisChannel)
                        else:
                            break

                ##begin print error returns
                for result in emptyRet:
                    if result['ret_']:
                        # begin print in client console
                        self._output_ret(result['ret_'], result['out'])

                for result in noResponseRet:
                    if result['ret_']:
                        for k, v in result['ret_'].items():
                            if k not in sucset:
                                # begin print in client console
                                self._output_ret(result['ret_'], result['out'])

                for result in noConnectRet:
                    if result['ret_']:
                        for k, v in result['ret_'].items():
                            if k not in sucset:
                                # begin print in client console
                                self._output_ret(result['ret_'], result['out'])

                disconnectedSyndic = set(comeSubList).difference(resultPingSet)
                if disconnectedSyndic:
                    print_cli('With disconnected syndic: %s' % list(disconnectedSyndic))

                if len(missedList) > 0 or len(lossSyndic) > 0:
                    print('missed maids: {}\nmissed minions: {}'.format(",".join(lossSyndic), ",".join(missedList)))

                if len(repeatet) > 0:
                    print('Find some minion run repeated: {}'.format(repeatet))

                global normalsize
                print('normal size: {}\nmissed size: {}\nempty size: {}'.format(normalsize, len(missedList),
                                                                                len(emptyRet)))
                redisChannel.unsubscribe(wrapMesage['tempTopic'])
                redisChannel.connection_pool.disconnect()

            def batchRun(wrapMesage, selfIp, clientPub, redisChannel):
                # NOTE: batch running mode
                # handle special syndic
                if selfIp in comeSubList:
                    comeSubList.remove(selfIp)

                syndic_count = len(comeSubList)
                resultCount = 0
                pingCount = 0

                executeStart = time.time()

                normalDone = False

                # NOTE: must publish cmd after registered the redis listen
                # else we will miss ping message
                # tmpKwargs1 = wrapMesage['kwargs']
                # batch_running = set(tmpKwargs1['tgt'])

                #print('publish wrapMesage: %s' % wrapMesage)
                clientPub.publishToSyndicSub(salt.newrun.json.dumps(wrapMesage))

                from salt.newrun import (json, byteify, MessageType)

                for message in redisChannel.listen():
                    try:
                        messageJson = byteify(message)
                        if messageJson['type'] == 'message':
                            resultMessage = messageJson['data']

                            try:

                                callResult = json.loads(resultMessage, encoding='utf-8')
                                callResult = byteify(callResult)

                                if isinstance(callResult, dict):
                                    if 'type' in callResult:
                                        messageType = callResult['type']
                                        messageIp = callResult['sub_ip']

                                        if messageType == MessageType.PING and messageIp in comeSubList:
                                            resultPingSet.append(messageIp)
                                        elif messageType == MessageType.WORK or messageType == MessageType.INTERRUPT:
                                            resultExeSet.append(messageIp)
                                        else:
                                            main_log.info('invalid callresult: %s' % callResult)

                                    else:
                                        # filter no return received of sub node
                                        retJsonObj = callResult['ret_']
                                        if retJsonObj:
                                            # reset start time
                                            executeStart = time.time()
                                            for k, v in retJsonObj.items():
                                                # reset running and wait node
                                                batch_running.discard(k)

                                            if callResult['out'] == 'no_return':
                                                if '[No response]' in json.dumps(retJsonObj):
                                                    noResponseRet.append(callResult)
                                                else:
                                                    noConnectRet.append(callResult)
                                            else:
                                                # put successed ip to tmp set
                                                for k, v in retJsonObj.items():
                                                    sucset.add(k)

                                                    # NOTE: debug
                                                    if k in debugSet:
                                                        repeatet.add(json.dumps(retJsonObj))
                                                    else:
                                                        debugSet.add(k)

                                                if callResult['retcode'] == 0:
                                                    isnil = False
                                                    for k in retJsonObj.keys():
                                                        v = retJsonObj[k]
                                                        if v == "":
                                                            isnil = True
                                                        break
                                                    if isnil:
                                                        emptyRet.append(callResult)
                                                    else:
                                                        global normalsize
                                                        normalsize += 1
                                                        self._output_ret(callResult['ret_'], callResult['out'])
                                                else:
                                                    emptyRet.append(callResult)

                                else:
                                    # TODO handle other messages?
                                    pass

                            except:
                                resultCount += 1
                                print_cli(traceback.format_exc())
                                pass

                        pingCount = len(resultPingSet)
                        resultCount = len(resultExeSet)

                        #from collections import Counter
                        #main_log.info("%s, %s, %s, %s" % (pingCount, resultCount, Counter(resultPingSet), Counter(resultExeSet)))
                        # if len(batch_init) <= 0:
                        #     break

                        if len(batch_running) == 0:
                            break

                        if pingCount != resultCount:
                            if (time.time() - executeStart) > sub_timeout:
                                # main_log.info("---T0 stop")
                                break
                    except:
                        main_log.info(traceback.format_exc())
                        pass



            def executeCallback(selfIp):
                redisChannel = clientPub.getRedisInstance().pubsub()
                redisChannel.subscribe(wrapMesage['tempTopic'])

                noResponseRet = []
                noConnectRet = []
                emptyRet = []
                # retcodes = []

                comeSubList = clientPub.pullAccept()

                # handle special syndic
                if selfIp in comeSubList:
                    comeSubList.remove(selfIp)

                syndic_count = len(comeSubList)
                resultCount = 0
                pingCount = 0

                resultPingSet = set()

                sucset = set()

                resultExeSet = set()

                debugSet = set()
                repeatet = set()

                lossSyndic = []

                executeStart = time.time()

                normalDone = False

                # NOTE: must publish cmd after registered the redis listen
                # else we will miss ping message
                clientPub.publishToSyndicSub(salt.newrun.json.dumps(wrapMesage))

                from salt.newrun import (json, byteify, MessageType)

                normalsize = 0

                for message in redisChannel.listen():
                    try:
                        messageJson = byteify(message)
                        if messageJson['type'] == 'message':
                            resultMessage = messageJson['data']

                            try:

                                callResult = json.loads(resultMessage, encoding='utf-8')
                                callResult = byteify(callResult)

                                if isinstance(callResult, dict):
                                    if 'type' in callResult:
                                        messageType = callResult['type']
                                        messageIp = callResult['sub_ip']

                                        if messageType == MessageType.PING and messageIp in comeSubList:
                                            resultPingSet.add(messageIp)
                                            pingCount += 1
                                        elif messageType == MessageType.WORK or messageType == MessageType.INTERRUPT:
                                            # main_log.info('work or interurupt: %s' % (messageIp))
                                            resultExeSet.add(messageIp)
                                            resultCount += 1
                                        else:
                                            main_log.info('invalid callresult: %s' % callResult)

                                    else:
                                        # filter no return received of sub node
                                        retJsonObj = callResult['ret_']
                                        if retJsonObj:
                                            # reset start time
                                            executeStart = time.time()
                                            if callResult['out'] == 'no_return':
                                                if '[No response]' in json.dumps(retJsonObj):
                                                    noResponseRet.append(callResult)
                                                else:
                                                    noConnectRet.append(callResult)

                                                # add to missed list
                                                for k, v in retJsonObj.items():
                                                    missedList.add(k)
                                            else:
                                                # put successed ip to tmp set
                                                for k, v in retJsonObj.items():
                                                    sucset.add(k)

                                                    # NOTE: debug
                                                    if k in debugSet:
                                                        repeatet.add(json.dumps(retJsonObj))
                                                    else:
                                                        debugSet.add(k)

                                                if callResult['retcode'] == 0:
                                                    isnil = False
                                                    for k in retJsonObj.keys():
                                                        v = retJsonObj[k]
                                                        if v == "":
                                                            isnil = True
                                                        break
                                                    if isnil:
                                                        emptyRet.append(callResult)
                                                    else:
                                                        normalsize += 1
                                                        self._output_ret(callResult['ret_'], callResult['out'])
                                                else:
                                                    emptyRet.append(callResult)

                                else:
                                    # TODO handle other messages?
                                    pass

                            except:
                                resultCount += 1
                                print_cli(traceback.format_exc())
                                pass

                        ##check sub timeout, if no node running again
                        #lossSyndic = [item for item in comeSubList if item not in resultExeSet]
                        #print(lossSyndic)

                        losePingCount = syndic_count - pingCount
                        runningCount = syndic_count - resultCount - losePingCount

                        #lossPing = [item for item in comeSubList if item not in resultPingSet]
                        #main_log.info("%s,%s,%s,%s,%s,%s" % (pingCount, syndic_count, runningCount, sub_timeout, executeStart, lossPing))

                        if pingCount < syndic_count and runningCount <= 0:
                            if (time.time() - executeStart) > sub_timeout:
                                main_log.info("---T0 stop")
                                break
                        elif syndic_count == pingCount and runningCount > 0:
                            if (time.time() - executeStart) > sub_timeout:
                                # main_log.info("---T1 stop")
                                break
                        elif syndic_count == pingCount and resultCount == syndic_count:
                            # main_log.info("---T2 stop")
                            break
                    except:
                        main_log.info(traceback.format_exc())
                        pass

                redisChannel.unsubscribe(wrapMesage['tempTopic'])
                redisChannel.connection_pool.disconnect()

                # main_log.info('---T: %s, %s, %s' % (emptyRet, noResponseRet, noConnectRet))

                ##begin print error returns
                for result in emptyRet:
                    if result['ret_']:
                        # begin print in client console
                        self._output_ret(result['ret_'], result['out'])

                for result in noResponseRet:
                    if result['ret_']:
                        for k, v in result['ret_'].items():
                            if k not in sucset:
                                # begin print in client console
                                self._output_ret(result['ret_'], result['out'])

                for result in noConnectRet:
                    if result['ret_']:
                        for k, v in result['ret_'].items():
                            if k not in sucset:
                                # begin print in client console
                                self._output_ret(result['ret_'], result['out'])

                disconnectedSyndic = set(comeSubList).difference(resultPingSet)
                if disconnectedSyndic:
                    print_cli('With disconnected syndic: %s' % list(disconnectedSyndic))

                if len(missedList) > 0 or len(lossSyndic) > 0:
                    print('missed maids: {}\nmissed minions: {}'.format(",".join(lossSyndic), ",".join(missedList)))

                if len(repeatet) > 0:
                    print('Find some minion run repeated: {}'.format(repeatet))

                print('normal size: {}\nmissed size: {}\nempty size: {}'.format(normalsize, len(missedList),
                                                                                len(emptyRet)))

                # NOTE: Return code is set here based on if all minions
                # returned 'ok' with a retcode of 0.
                # This is the final point before the 'salt' cmd returns,
                # which is why we set the retcode here.
                # if retcodes.count(0) < len(retcodes):
                #     sys.stderr.write('ERROR: Minions returned with non-zero exit code\n')
                #     sys.exit(11)

            if self.options.batch:
                bwait = self.config.get('batch_wait', 0)
                redisChannel = clientPub.getRedisInstance().pubsub()

                percentBatch = 0.0
                try:
                    if self.options.batch.endswith('%'):
                        stripBatch = float(self.options.batch.strip('%'))
                        percentBatch = stripBatch/100
                    else:
                        batch_hold = int(self.options.batch)
                except:
                    print('An Int or Percent can be used for batch.')
                    return

                # find all ip list
                if kwargs['tgt'] == '*':
                    reGetAllMinionList = []
                    wrapFindAcceptMesage = {'type': salt.newrun.FunctionType.FIND_ACCEPT, 'tempTopic': ('fa_%s' % str(salt.newrun.uuid.uuid1()))}
                    redisChannel.subscribe(wrapFindAcceptMesage['tempTopic'])
                    clientPub.publishToSyndicSub(salt.newrun.json.dumps(wrapFindAcceptMesage))

                    from salt.newrun import (json, byteify, MessageType)
                    ping1stCount = 0
                    work1stcount = 0
                    for message in redisChannel.listen():
                        try:
                            messageJson = byteify(message)
                            if messageJson['type'] == 'message':
                                resultMessage = messageJson['data']

                                try:
                                    callResult = json.loads(resultMessage, encoding='utf-8')
                                    callResult = byteify(callResult)

                                    if isinstance(callResult, dict):
                                        if 'type' in callResult:
                                            messageType = callResult['type']
                                            messageIp = callResult['sub_ip']

                                            if messageType == MessageType.PING and messageIp in comeSubList:
                                                ping1stCount += 1
                                            elif messageType == MessageType.WORK or messageType == MessageType.INTERRUPT:
                                                work1stcount += 1
                                                if ping1stCount == work1stcount and work1stcount==len(comeSubList):
                                                    break
                                            else:
                                                main_log.info('invalid callresult: %s' % callResult)

                                        else:
                                            # filter no return received of sub node
                                            retJsonObj = callResult['ip_list']
                                            if retJsonObj:
                                                reGetAllMinionList = reGetAllMinionList + retJsonObj
                                    else:
                                        pass
                                        #print('callResult: %s' % callResult)
                                except:
                                    main_log.info(traceback.format_exc())
                                    pass
                        except:
                            main_log.info(traceback.format_exc())
                            pass

                    kwargs['tgt'] = reGetAllMinionList
                    batch_init = set(kwargs['tgt'])

                    redisChannel.unsubscribe(wrapFindAcceptMesage['tempTopic'])
                    redisChannel.connection_pool.disconnect()

                else:
                    if kwargs['tgt_type'] == 'glob':
                        batch_init.add(kwargs['tgt'])
                    else:
                        batch_init = set(kwargs['tgt'])

                kwargs['tgt_type'] = 'list'
                wrapMesage['kwargs'] = kwargs

                if percentBatch > 0:
                    batch_hold = percentBatch * len(batch_init)

                redisChannel.subscribe(wrapMesage['tempTopic'])
                batchExecuteCallback(self.newopt['id'], clientPub, redisChannel)
            else:
                executeCallback(self.newopt['id'])





    def run(self):
        # '''
        # Execute the salt command line
        # '''
        import salt.client
        # self.parse_args()

        # Setup file logging!
        self.setup_logfile_logger()
        verify_log(self.config)

        try:
            # We don't need to bail on config file permission errors
            # if the CLI
            # process is run with the -a flag
            skip_perm_errors = self.options.eauth != ''

            self.local_client = salt.client.get_local_client(
                self.get_config_file_path(),
                skip_perm_errors=skip_perm_errors,
                auto_reconnect=True)
        except SaltClientError as exc:
            self.exit(2, '{0}\n'.format(exc))
            return

        if self.options.batch or self.options.static:
            # _run_batch() will handle all output and
            # exit with the appropriate error condition
            # Execution will not continue past this point
            # in batch mode.
            self._run_batch()
            return

        if self.options.preview_target:
            self._preview_target()
            return

        if self.options.timeout <= 0:
            self.options.timeout = self.local_client.opts['timeout']

        kwargs = {
            'tgt': self.config['tgt'],
            'fun': self.config['fun'],
            'arg': self.config['arg'],
            'timeout': self.options.timeout,
            'show_timeout': self.options.show_timeout,
            'show_jid': self.options.show_jid}

        if 'token' in self.config:
            try:
                with salt.utils.fopen(os.path.join(self.config['cachedir'], '.root_key'), 'r') as fp_:
                    kwargs['key'] = fp_.readline()
            except IOError:
                kwargs['token'] = self.config['token']

        kwargs['delimiter'] = self.options.delimiter

        if self.selected_target_option:
            kwargs['tgt_type'] = self.selected_target_option
        else:
            kwargs['tgt_type'] = 'glob'

        if getattr(self.options, 'return'):
            kwargs['ret'] = getattr(self.options, 'return')

        if getattr(self.options, 'return_config'):
            kwargs['ret_config'] = getattr(self.options, 'return_config')

        if getattr(self.options, 'return_kwargs'):
            kwargs['ret_kwargs'] = yamlify_arg(
                getattr(self.options, 'return_kwargs'))

        if getattr(self.options, 'module_executors'):
            kwargs['module_executors'] = yamlify_arg(getattr(self.options, 'module_executors'))

        if getattr(self.options, 'metadata'):
            kwargs['metadata'] = yamlify_arg(
                getattr(self.options, 'metadata'))

        # If using eauth and a token hasn't already been loaded into
        # kwargs, prompt the user to enter auth credentials
        if 'token' not in kwargs and 'key' not in kwargs and self.options.eauth:
            # This is expensive. Don't do it unless we need to.
            import salt.auth
            resolver = salt.auth.Resolver(self.config)
            res = resolver.cli(self.options.eauth)
            if self.options.mktoken and res:
                tok = resolver.token_cli(
                    self.options.eauth,
                    res
                )
                if tok:
                    kwargs['token'] = tok.get('token', '')
            if not res:
                sys.stderr.write('ERROR: Authentication failed\n')
                sys.exit(2)
            kwargs.update(res)
            kwargs['eauth'] = self.options.eauth

        if self.config['async']:
            jid = self.local_client.cmd_async(**kwargs)
            print_cli('Executed command with job ID: {0}'.format(jid))
            return

        # local will be None when there was an error
        if not self.local_client:
            return

        retcodes = []
        errors = []
        try:
            if self.options.subset:
                cmd_func = self.local_client.cmd_subset
                kwargs['sub'] = self.options.subset
                kwargs['cli'] = True
            else:
                cmd_func = self.local_client.cmd_cli

            if self.options.progress:
                kwargs['progress'] = True
                self.config['progress'] = True
                ret = {}
                for progress in cmd_func(**kwargs):
                    out = 'progress'
                    try:
                        self._progress_ret(progress, out)
                    except salt.exceptions.LoaderError as exc:
                        raise salt.exceptions.SaltSystemExit(exc)
                    if 'return_count' not in progress:
                        ret.update(progress)
                self._progress_end(out)
                self._print_returns_summary(ret)
            elif self.config['fun'] == 'sys.doc':
                ret = {}
                out = ''
                for full_ret in self.local_client.cmd_cli(**kwargs):
                    ret_, out, retcode = self._format_ret(full_ret)
                    ret.update(ret_)
                self._output_ret(ret, out)
            else:
                if self.options.verbose:
                    kwargs['verbose'] = True
                ret = {}

                # TODO: delete debug code start=============================
                # import re
                # import subprocess
                # from salt.newrun import (json, byteify, MessageType)

                # oriArr = []
                # executeArr = []
                # def executeSaltCmd(cmd, msg_in=''):
                #     try:
                #         proc = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE,
                #                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE,)
                #         stdout_value, stderr_value = proc.communicate(msg_in)

                #         return stdout_value, stderr_value
                #     except Exception, e:
                #         log.error(traceback.format_exc())
                #         #print('traceback.format_exc():\n%s' % traceback.format_exc())

                # def getAcceptIp():
                #     stdout_val, stderr_val = executeSaltCmd("salt-key -l acc")
                #     syndicList = re.findall(
                #         r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b", stdout_val, re.M)
                #     return syndicList

                # oriArr = getAcceptIp()
                # loopi = 0
                # TODO: delete debug code end=============================
                for full_ret in cmd_func(**kwargs):
                    try:
                        ret_, out, retcode = self._format_ret(full_ret)
                        # print('full_ret=: %s, ret_=: %s, out=: %s' % (full_ret, ret_, out))

                        retcodes.append(retcode)
                        self._output_ret(ret_, out)

                        # TODO: delete debug code start=============================
                        # ret_ = byteify(ret_)
                        # ssList = re.findall(r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b", json.dumps(ret_), re.M)
                        # executeArr = executeArr + ssList
                        # loopi = loopi +1
                        # if loopi > 2516:
                        #     eprint = [i for i in oriArr if i not in executeArr]
                        #     print(eprint)
                        # TODO: delete debug code end=============================

                        ret.update(full_ret)
                    except KeyError:
                        errors.append(full_ret)

            # Returns summary
            if self.config['cli_summary'] is True:
                if self.config['fun'] != 'sys.doc':
                    if self.options.output is None:
                        self._print_returns_summary(ret)
                        self._print_errors_summary(errors)

            # NOTE: Return code is set here based on if all minions
            # returned 'ok' with a retcode of 0.
            # This is the final point before the 'salt' cmd returns,
            # which is why we set the retcode here.
            if retcodes.count(0) < len(retcodes):
                sys.stderr.write('ERROR: Minions returned with non-zero exit code\n')
                sys.exit(11)

        except (SaltInvocationError, EauthAuthenticationError, SaltClientError) as exc:
            ret = str(exc)
            self._output_ret(ret, '')

    def _preview_target(self):
        '''
        Return a list of minions from a given target
        '''
        minion_list = self.local_client.gather_minions(self.config['tgt'], self.selected_target_option or 'glob')
        self._output_ret(minion_list, self.config.get('output', 'nested'))

    def _run_batch(self):
        import salt.cli.batch
        eauth = {}
        if 'token' in self.config:
            eauth['token'] = self.config['token']

        # If using eauth and a token hasn't already been loaded into
        # kwargs, prompt the user to enter auth credentials
        if 'token' not in eauth and self.options.eauth:
            # This is expensive. Don't do it unless we need to.
            import salt.auth
            resolver = salt.auth.Resolver(self.config)
            res = resolver.cli(self.options.eauth)
            if self.options.mktoken and res:
                tok = resolver.token_cli(
                    self.options.eauth,
                    res
                )
                if tok:
                    eauth['token'] = tok.get('token', '')
            if not res:
                sys.stderr.write('ERROR: Authentication failed\n')
                sys.exit(2)
            eauth.update(res)
            eauth['eauth'] = self.options.eauth

        if self.options.static:

            if not self.options.batch:
                self.config['batch'] = '100%'

            try:
                batch = salt.cli.batch.Batch(self.config, eauth=eauth, quiet=True)
            except salt.exceptions.SaltClientError as exc:
                sys.exit(2)

            ret = {}

            for res in batch.run():
                ret.update(res)

            self._output_ret(ret, '')

        else:
            try:
                batch = salt.cli.batch.Batch(self.config, eauth=eauth, parser=self.options)
            except salt.exceptions.SaltClientError as exc:
                # We will print errors to the console further down the stack
                sys.exit(1)
            # Printing the output is already taken care of in run() itself
            retcode = 0
            for res in batch.run():
                for ret in six.itervalues(res):
                    job_retcode = salt.utils.job.get_retcode(ret)
                    if job_retcode > retcode:
                        # Exit with the highest retcode we find
                        retcode = job_retcode
                    if self.options.failhard:
                        if retcode != 0:
                            sys.stderr.write(
                                '{0}\nERROR: Minions returned with non-zero exit code.\n'.format(
                                    res
                                )
                            )
                            sys.exit(retcode)
            sys.exit(retcode)

    def _print_errors_summary(self, errors):
        if errors:
            print_cli('\n')
            print_cli('---------------------------')
            print_cli('Errors')
            print_cli('---------------------------')
            for error in errors:
                print_cli(self._format_error(error))

    def _print_returns_summary(self, ret):
        '''
        Display returns summary
        '''
        return_counter = 0
        not_return_counter = 0
        not_return_minions = []
        not_response_minions = []
        not_connected_minions = []
        failed_minions = []
        for each_minion in ret:
            minion_ret = ret[each_minion]
            if isinstance(minion_ret, dict) and 'ret' in minion_ret:
                minion_ret = ret[each_minion].get('ret')
            if (
                    isinstance(minion_ret, string_types)
                    and minion_ret.startswith("Minion did not return")
            ):
                if "Not connected" in minion_ret:
                    not_connected_minions.append(each_minion)
                elif "No response" in minion_ret:
                    not_response_minions.append(each_minion)
                not_return_counter += 1
                not_return_minions.append(each_minion)
            else:
                return_counter += 1
                if self._get_retcode(ret[each_minion]):
                    failed_minions.append(each_minion)
        print_cli('\n')
        print_cli('-------------------------------------------')
        print_cli('Summary')
        print_cli('-------------------------------------------')
        print_cli('# of minions targeted: {0}'.format(return_counter + not_return_counter))
        print_cli('# of minions returned: {0}'.format(return_counter))
        print_cli('# of minions that did not return: {0}'.format(not_return_counter))
        print_cli('# of minions with errors: {0}'.format(len(failed_minions)))
        if self.options.verbose:
            if not_connected_minions:
                print_cli('Minions not connected: {0}'.format(" ".join(not_connected_minions)))
            if not_response_minions:
                print_cli('Minions not responding: {0}'.format(" ".join(not_response_minions)))
            if failed_minions:
                print_cli('Minions with failures: {0}'.format(" ".join(failed_minions)))
        print_cli('-------------------------------------------')

    def _progress_end(self, out):
        import salt.output
        salt.output.progress_end(self.progress_bar)

    def _progress_ret(self, progress, out):
        '''
        Print progress events
        '''
        import salt.output
        # Get the progress bar
        if not hasattr(self, 'progress_bar'):
            try:
                self.progress_bar = salt.output.get_progress(self.config, out, progress)
            except Exception as exc:
                raise salt.exceptions.LoaderError('\nWARNING: Install the `progressbar` python package. '
                                                  'Requested job was still run but output cannot be displayed.\n')
        salt.output.update_progress(self.config, progress, self.progress_bar, out)

    def _output_ret(self, ret, out):
        '''
        Print the output from a single return to the terminal
        '''
        import salt.output
        # Handle special case commands
        if self.config['fun'] == 'sys.doc' and not isinstance(ret, Exception):
            self._print_docs(ret)
        else:
            # Determine the proper output method and run it
            salt.output.display_output(ret, out, self.config)
        if not ret:
            sys.stderr.write('ERROR: No return received\n')
            sys.exit(2)

    def _output_ret_v2(self, ret, out, **kwargs):
        '''
        Print the output from a single return to the terminal
        '''
        import salt.output
        # Handle special case commands
        # Determine the proper output method and run it
        salt.output.display_output(ret, out, **kwargs)
        if not ret:
            sys.stderr.write('ERROR: No return received\n')
            sys.exit(2)

    def _format_ret(self, full_ret):
        '''
        Take the full return data and format it to simple output
        '''
        ret = {}
        out = ''
        retcode = 0
        for key, data in six.iteritems(full_ret):
            ret[key] = data['ret']
            if 'out' in data:
                out = data['out']
            ret_retcode = self._get_retcode(data)
            if ret_retcode > retcode:
                retcode = ret_retcode
        return ret, out, retcode

    def _get_retcode(self, ret):
        '''
        Determine a retcode for a given return
        '''
        retcode = 0
        # if there is a dict with retcode, use that
        if isinstance(ret, dict) and ret.get('retcode', 0) != 0:
            return ret['retcode']
        # if its a boolean, False means 1
        elif isinstance(ret, bool) and not ret:
            return 1
        return retcode

    def _format_error(self, minion_error):
        for minion, error_doc in six.iteritems(minion_error):
            error = 'Minion [{0}] encountered exception \'{1}\''.format(minion, error_doc['message'])
        return error

    def _print_docs(self, ret):
        '''
        Print out the docstrings for all of the functions on the minions
        '''
        import salt.output
        docs = {}
        if not ret:
            self.exit(2, 'No minions found to gather docs from\n')
        if isinstance(ret, str):
            self.exit(2, '{0}\n'.format(ret))
        for host in ret:
            if isinstance(ret[host], string_types) \
                    and (ret[host].startswith("Minion did not return")
                         or ret[host] == 'VALUE_TRIMMED'):
                continue
            for fun in ret[host]:
                if fun not in docs and ret[host][fun]:
                    docs[fun] = ret[host][fun]
        if self.options.output:
            for fun in sorted(docs):
                salt.output.display_output({fun: docs[fun]}, 'nested', self.config)
        else:
            for fun in sorted(docs):
                print_cli('{0}:'.format(fun))
                print_cli(docs[fun])
                print_cli('')
