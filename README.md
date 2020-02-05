==================
What is SaltStack?
==================

SaltStack makes software for complex systems management at scale.
SaltStack is the company that created and maintains the Salt Open
project and develops and sells SaltStack Enterprise software, services
and support. Easy enough to get running in minutes, scalable enough to
manage tens of thousands of servers, and fast enough to communicate with
them in *seconds*.

Salt is a new approach to infrastructure management built on a dynamic
communication bus. Salt can be used for data-driven orchestration,
remote execution for any infrastructure, configuration management for
any app stack, and much more.

Download Salt Open
==================

Salt Open is tested and packaged to run on CentOS, Debian, RHEL, Ubuntu,
Windows. Download Salt Open and get started now.

`<https://repo.saltstack.com/>`_

`Installation Instructions <https://docs.saltstack.com/en/latest/topics/installation/index.html>`_

SaltStack Documentation
=======================

Installation instructions, getting started guides, and in-depth API
documentation.

`<https://docs.saltstack.com/en/getstarted/>`_

`<https://docs.saltstack.com/en/latest/>`_

Get SaltStack Support and Help
==============================

**IRC Chat** - Join the vibrant, helpful and positive SaltStack chat room in
Freenode at #salt. There is no need to introduce yourself, or ask permission to
join in, just help and be helped! Make sure to wait for an answer, sometimes it
may take a few moments for someone to reply.

`<http://webchat.freenode.net/?channels=salt&uio=Mj10cnVlJjk9dHJ1ZSYxMD10cnVl83>`_

**Mailing List** - The SaltStack community users mailing list is hosted by
Google groups. Anyone can post to ask questions about SaltStack products and
anyone can help answer. Join the conversation!

`<https://groups.google.com/forum/#!forum/salt-users>`_

You may subscribe to the list without a Google account by emailing
salt-users+subscribe@googlegroups.com and you may post to the list by emailing
salt-users@googlegroups.com

**Reporting Issues** - To report an issue with Salt, please follow the
guidelines for filing bug reports:
`<https://docs.saltstack.com/en/develop/topics/development/reporting_bugs.html>`_

**SaltStack Support** - If you need dedicated, prioritized support, please
consider a SaltStack Support package that fits your needs:
`<http://www.saltstack.com/support>`_

Engage SaltStack
================

`SaltConf`_, **User Groups and Meetups** - SaltStack has a vibrant and `global
community`_ of customers, users, developers and enthusiasts. Connect with other
Salted folks in your area of the world, or join `SaltConf18`_, the SaltStack
annual user conference, September 10-14 in Salt Lake City. Please let us know if
you would like to start a user group or if we should add your existing
SaltStack user group to this list by emailing: info@saltstack.com

**SaltStack Training** - Get access to proprietary `SaltStack education
offerings`_ through instructor-led training offered on-site, virtually or at
SaltStack headquarters in Salt Lake City. SaltStack Enterprise training helps
increase the value and effectiveness of SaltStack software for any customer and
is a prerequisite for coveted `SaltStack Certified Engineer (SSCE)`_ status.
SaltStack training is also available through several `SaltStack professional
services`_ offerings.

**Follow SaltStack on -**

* YouTube - `<http://www.youtube.com/saltstack>`_
* Twitter - `<http://www.twitter.com/saltstack>`_
* Facebook - `<https://www.facebook.com/SaltStack/>`_
* LinkedIn - `<https://www.linkedin.com/company/salt-stack-inc>`_
* LinkedIn Group - `<https://www.linkedin.com/groups/4877160>`_
* Google+ - `<https://plus.google.com/b/112856352920437801867/+SaltStackInc/posts>`_

.. _SaltConf: http://www.youtube.com/user/saltstack
.. _global community: http://www.meetup.com/pro/saltstack/
.. _SaltConf18: http://saltconf.com/
.. _SaltStack education offerings: http://saltstack.com/training/
.. _SaltStack Certified Engineer (SSCE): http://saltstack.com/certification/
.. _SaltStack professional services: http://saltstack.com/services/

Developing Salt
===============

The Salt development team is welcoming, positive, and dedicated to
helping people get new code and fixes into SaltStack projects. Log into
GitHub and get started with one of the largest developer communities in
the world. The following links should get you started:

`<https://github.com/saltstack>`_

`<https://docs.saltstack.com/en/latest/topics/development/index.html>`_

`<https://docs.saltstack.com/en/develop/topics/development/pull_requests.html>`_

==================
安装引导
==================

1.源码直接安装

2.RPM打包

3.RPM安装

4.架构说明


源码安装
===============

* git clone http://git.jd.com/saltstack/salt.git

* 进入/salt/录下，执行./setup.py install，会在/usr/bin/目录下生成salt-maid、saltx、salt-apiv2等启动脚本
* salt-maid：salt-syndic的替代品，运行在salts-syndic节点
* salt-apiv2：salt-api的替代品，运行在salt-master节点
* salt：基于redis pub/sub重构优化的salt命令
* saltx：官方原生salt命令，已废弃

RPM打包
===============

* 安装rpm：yum install rpmdevtools && yum install -y rpm-build && rpmdev-setuptree
* 创建rpm工作区目录：
    ~/rpmbuild/BUILD  ~/rpmbuild/BUILDROOT  ~/rpmbuild/RPMS  ~/rpmbuild/SOURCES  ~/rpmbuild/SPECS  ~/rpmbuild/SRPMS
* 修改/salt/pkg/rpm下salt.spec文件：Version以及%global srcver字段修改为新版本号
* 修改/salt/_version.py中版本号，与salt.spec一致
* 将/salt打包为salt-x.x.x.tar.gz，将salt-x.x.x.tar.gz放入/root/rpmbuild/SOURCES/
* 将/salt/pkg/rpm/下所有文件放入/root/rpmbuild/SOURCES/
* 进入/salt/pkg/rpm/，执行rpmbuild -bb salt.spec
* 构建好的rpm包在/root/rpmbuild/RPMS/noarch/下

RPM安装
===============
* 说明：使用yum本地安装模式
* 步骤：将RPM包放入任意目录下，执行：yum localinstall salt-2019.1.18-1.el7.centos.noarch.rpm salt-master-2019.1.18-1.el7.centos.noarch.rpm salt-minion-2019.1.18-1.el7.centos.noarch.rpm salt-syndic-2019.1.18-1.el7.centos.noarch.rpm salt-maid-2019.1.18-1.el7.centos.noarch.rpm

架构说明
===============

* 重构架构图
<p align="center">
<img src="hhttps://github.com/andyyumiao/saltx/blob/master/doc/201904041031-29f9db5a-4d5d-4c3b-bff7-0c414c4b943dmax.png" alt="SaltStrcut" title="SaltStrcut" />
</p>


* 重构启动流程
<p align="center">
<img src="http://storage.jd.com/bdp-uploaded-files/201904041033-1bb4a1bb-5921-446e-ad10-cd4a46269e6dmax.png?Expires=3701828859&AccessKey=6f4e945a1d556e6d87d9bf41c7cdfc3f11da2dc2&Signature=TIlhfVZLiUy8hYOBt5vXW60xUkw%3D" alt="SaltBoot" title="SaltBoot" />
</p>

