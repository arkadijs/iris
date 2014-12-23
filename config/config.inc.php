<?php
$config = array();
$config['db_dsnw'] = 'mysql://roundcube:{{mysql_rcub_password}}@localhost/roundcubemail';
$config['default_host'] = '127.0.0.1';
$config['default_port'] = 144;
$config['des_key'] = '{{rcub_random}}';
$config['draft_autosave'] = 60;
$config['enable_installer'] = true;
$config['enable_spellcheck'] = false;
$config['imap_cache'] = 'memcache';
$config['ip_check'] = true;
$config['memcache_hosts'] = array('localhost:11211');
$config['mime_types'] = '/usr/share/misc/mime.types';
$config['plugins'] = array('archive', 'zipdownload', 'vacation');
$config['preview_pane'] = true;
$config['product_name'] = 'Webmail';
$config['skin'] = 'larry';
$config['smtp_server'] = '127.0.0.1';
?>
