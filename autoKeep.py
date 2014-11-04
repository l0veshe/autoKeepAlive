#!/bin/env python
# -*- coding: utf-8 -*-
#from optparse import OptionParser
import os,sys, re, json
from os import path, access, R_OK  # W_OK for write permission


#用户需求常量##################################
CURREND_PATH, B = os.path.split(os.path.abspath(sys.argv[0]))		##本程序位置
#currentpath = "/a/b/c/d"
CFG_PATH = CURREND_PATH + "/config"	##配置文件的文件夹位置
END_CFG = ".cfg"					##配置文件尾缀
VERSION = "0.4"
#############################################
OUT_FILE = "/tmp/keepalived.conf"
#模板#########################################
FILE_HEAD="""#configure for keepalived by dongjin@limei.com,human.gold@gmail.com
#global define

global_defs {
    notification_email {
    dongjin@limei.com
    op@limei.com
    }
    notification_email_from op-robot@limei.com
    smtp_server 127.0.0.1
    smtp_connect_timeout 30
    router_id LVS_ADN
}
"""

FILEGROUP="""#############################
vrrp_sync_group %s{
    group {
            %s
          }
}
#############################
"""

FILE_VIP="""#############################
#%s#
#############################
vrrp_instance %s{
	state %s
	interface %s
	lvs_sync_daemon_interface %s
	virtual_router_id %s
	priority %s
	advert_int 1
	authentication {
		auth_type %s
		auth_pass %s
	}
	virtual_ipaddress {
		%s
	}
}
"""

FILE_VIRTUAL="""virtual_server %s %s {
    delay_loop 2
    lb_algo wlc
    lb_kind DR
    persistence_timeout %s
    protocol TCP

"""

FILE_REAL="""    real_server %s %s {
        weight 100
        MISC_CHECK {
            misc_path "/etc/keepalived/TCP_CHECK.sh %s  %s"
            misc_timeout 5
            misc_dynamic
        }
    }
"""

FILE_VIRTUAL_END="""
}
"""
FILE_CLIENT="""#!/bin/bash

VIP1=%s

. /etc/rc.d/init.d/functions

case "$1" in
start)
	ifconfig lo:1 $VIP1 netmask 255.255.255.255 broadcast $VIP1 up
	echo  "1"  > /proc/sys/net/ipv4/conf/lo/arp_ignore
	echo  "2"  > /proc/sys/net/ipv4/conf/lo/arp_announce
	echo  "1"  > /proc/sys/net/ipv4/conf/all/arp_ignore
	echo  "2"  > /proc/sys/net/ipv4/conf/all/arp_announce
	echo "RealServer Start  OK"

	;;

stop)
	ifconfig lo:1 down
	echo  "0"  > /proc/sys/net/ipv4/conf/lo/arp_ignore
	echo  "0"  > /proc/sys/net/ipv4/conf/lo/arp_announce
	echo  "0"  > /proc/sys/net/ipv4/conf/all/arp_ignore
	echo  "0"  > /proc/sys/net/ipv4/conf/all/arp_announce
	echo  "RealServer Stop "
	;;
*)
	echo "Usage: $0{start|stop}"
	exit 1
esac
"""
############################################

#tools:返回所有配置文件
#Return type:list
def findCfg(endCfg,cfgPath):	
	pattern = '^.+\\' + endCfg + '$'
	cfgList = []  
	curList = os.listdir(cfgPath)     
	for item in curList:     
		p = re.compile(pattern)
		if p.match(item):
			cfgList.append(cfgPath + "/" + item)
	return cfgList

#配置文件转json
#Return type:dict, str 
def file2json(cfgPath):
	fileCfgObject = open(cfgPath)
	try:
		fileJson = fileCfgObject.read()
	finally:
		fileCfgObject.close()
	fileJsonObject = json.loads(fileJson)
	fileJsonObjectName = fileJsonObject['vrrp_group_name']
	return fileJsonObject,fileJsonObjectName

#检查脚本语法
def examineCfg():
	print "检测配置文件语法..." + "OK"

#读取所有配置文件
#Return type: dict
def stdinCfg():
	cfgList = []
	cfgDict = {}
	if path.exists(CFG_PATH) and path.isdir(CFG_PATH) and access(CFG_PATH, R_OK):
		examineCfg()
		cfgList = findCfg(END_CFG, CFG_PATH)
		if len(cfgList):
			for cfgPath in cfgList:
				cfgJsonItem,cfgJsonItemName = file2json(cfgPath)
				cfgDict[cfgJsonItemName] = cfgJsonItem
	else:
		print "配置文件夹不存在或不可写"
	return cfgDict	

#生成客户端启动脚本
def generateClientFile(group,vipp,ip):
	clientScriptName = "lvs_real_" + group
	clientScriptPath = "/tmp/" + clientScriptName
	clientScriptStr = FILE_CLIENT % (vipp)
	stdoutObject = open("/tmp/" + clientScriptName,'w')
	try:
		stdoutObject.write(clientScriptStr)
	finally:
		stdoutObject.close()
	print "请发送 ".decode('utf-8') + clientScriptPath + " 到 ".decode('utf-8') + ip + ":/usr/local/bin/"
#脚本生成主函数
def generate():
	allInfoDict = stdinCfg()
	keepalived=FILE_HEAD
	keepalived2=FILE_HEAD
	keepalivedGroup = ""
	keepalivedVrrp = ""
	keepalivedVrrp2 = ""
	keepalivedVirtual = ""

	for keys in allInfoDict:
		groupName = keys
		for keys2 in allInfoDict[keys]['group']:
			group = keys2
			keepalivedGroup = keepalivedGroup + FILEGROUP % (groupName, group)
			interface = allInfoDict[keys]['group'][keys2]['interface']
			authType =  allInfoDict[keys]['group'][keys2]['auth_type']
			authPass =  allInfoDict[keys]['group'][keys2]['auth_pass']
			vipp = allInfoDict[keys]['group'][keys2]['virtual']['vip']
			routerId = allInfoDict[keys]['group'][keys2]['virtual']['router_ip']
			perTime = allInfoDict[keys]['group'][keys2]['virtual']['per_time']
			for keys5 in allInfoDict[keys]['group'][keys2]['virtual']['real_server']:
				ip = keys5
				generateClientFile(group,vipp, ip)
			keepalivedVrrp = keepalivedVrrp + FILE_VIP % (group, group, "MASTER", interface, interface, routerId, "100", authType, authPass, vipp)
			keepalivedVrrp2 = keepalivedVrrp2 + FILE_VIP % (group, group, "BACKUP", interface, interface, routerId,  "90", authType, authPass, vipp)
			for keys3 in allInfoDict[keys]['group'][keys2]['virtual']['port']:
				port = keys3
				keepalivedVirtual = keepalivedVirtual + FILE_VIRTUAL % (vipp, port, perTime)
				for keys4 in allInfoDict[keys]['group'][keys2]['virtual']['real_server']:
					ip = keys4
					keepalivedVirtual = keepalivedVirtual + FILE_REAL % (ip, port, ip, port)
				keepalivedVirtual = keepalivedVirtual + FILE_VIRTUAL_END
	#print keepalivedGroup
	#print keepalivedVrrp
	#print keepalivedVirtual
	keepalived = keepalived + keepalivedGroup + keepalivedVrrp + keepalivedVirtual
	keepalived2 = keepalived2 + keepalivedGroup + keepalivedVrrp2 + keepalivedVirtual
	stdoutObject = open(OUT_FILE + ".master",'w')
	stdoutObject2 = open(OUT_FILE + ".backup",'w')
	try:
		stdoutObject.write(keepalived)
		stdoutObject2.write(keepalived2)
	finally:
		stdoutObject.close()
		stdoutObject2.close()
	print "主配置文件保存到 %s.master" % OUT_FILE
	print "备配置文件保存到 %s.backup" % OUT_FILE
	return keepalived

#获取执行命令参数
def parse():
	print "######董金电话:18601069608##########"
        print "######HANK电话:15804268950##########"
	#opt = OptionParser()
	keepalived = generate()

if __name__ == "__main__":
	parse()
	print "Generate completed!"
        print "Power by Hank,Version is %s." % (VERSION)
