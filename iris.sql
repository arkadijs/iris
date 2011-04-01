CREATE TABLE `accounts` (
  `id` int(11) NOT NULL auto_increment,
  `account` varchar(100) NOT NULL default '',
  `pwd` varchar(20) NOT NULL default '',
  `local_part` varchar(100) NOT NULL default '',
  `domain` varchar(100) NOT NULL default '',
  `first_name` varchar(100) default NULL,
  `surname` varchar(100) default NULL,
  `phone` varchar(30) default NULL,
  `other_email` varchar(100) default NULL,
  `info` varchar(250) default NULL,
  `quota` int(11) NOT NULL default '0',
  `overquota` tinyint(1) NOT NULL default '0',
  `disabled` tinyint(1) NOT NULL default '0',
  `smtp_auth` tinyint(1) NOT NULL default '0',
  `vacation` tinyint(1) NOT NULL default '0',
  `vacation_text` text,
  `av_disabled` tinyint(1) NOT NULL default '0',
  `superuser` tinyint(1) NOT NULL default '0',
  `admin_quota` int(11) NOT NULL default '0',
  `admin_accounts` int(11) NOT NULL default '0',
  `admin_max_quota` int(11) NOT NULL default '0',
  `admin_max_accounts` int(11) NOT NULL default '0',
  PRIMARY KEY  (`id`),
  UNIQUE KEY `account` (`account`),
  KEY `domain` (`domain`)
);

CREATE TABLE `aliases` (
  `id` int(11) NOT NULL auto_increment,
  `alias` varchar(100) NOT NULL default '',
  `local_part` varchar(100) NOT NULL default '',
  `domain` varchar(100) NOT NULL default '',
  `aliased_to` text NOT NULL,
  PRIMARY KEY  (`id`),
  UNIQUE KEY `alias` (`alias`),
  KEY `domain` (`domain`)
);

CREATE TABLE `domains` (
  `id` int(11) NOT NULL auto_increment,
  `domain` varchar(100) NOT NULL default '',
  `info` varchar(250) default NULL,
  `disabled` tinyint(1) NOT NULL default '0',
  `smtp_auth` tinyint(1) NOT NULL default '0',
  `non_local` tinyint(1) NOT NULL default '0',
  PRIMARY KEY  (`id`),
  UNIQUE KEY `domain` (`domain`)
);

CREATE TABLE `greylist` (
  `id` int(11) NOT NULL auto_increment,
  `relay_ip` varchar(64) default NULL,
  `from_domain` varchar(255) default NULL,
  `block_expires` datetime NOT NULL default '0000-00-00 00:00:00',
  `record_expires` datetime NOT NULL default '0000-00-00 00:00:00',
  `origin_type` enum('MANUAL','AUTO') NOT NULL default 'AUTO',
  `create_time` datetime NOT NULL default '0000-00-00 00:00:00',
  PRIMARY KEY  (`id`),
  KEY `relay_ip` (`relay_ip`(15),`from_domain`(20))
);

CREATE TABLE `managed_domains` (
  `acc_id` int(11) NOT NULL default '0',
  `dom_id` int(11) NOT NULL default '0',
  KEY `admin_domains` (`acc_id`),
  KEY `domain_admins` (`dom_id`)
);

insert into domains (id, domain) values (1, 'admin.domain');
insert into accounts (id, account, pwd, superuser, local_part, domain) values (1, 'admin', 'superuserpassword', 1, 'admin', 'admin.domain');
