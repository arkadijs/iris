<?php
   // global variables - don't touch these unless you want to break the plugin
   global $mysql_server, $mysql_user, $mysql_pwd, $mysql_database,
          $mysql_table, $mysql_userid, $mysql_vacation, $mysql_vacation_text;

   // MySQL server, socket is optional
   $mysql_server = 'localhost:/tmp/mysql.sock41';

   // the MySQL user ID
   $mysql_user = 'iris';

   // the MySQL user's password
   $mysql_pwd = 'password2';

   // the MySQL database that contains email account information
   $mysql_database = 'mail';

   // the MySQL table that contains email account information
   $mysql_table = 'accounts';

   // the MySQL field that contains users' IDs
   $mysql_userid = 'account';

   // the MySQL field that contains users' vacation status flag 0/1
   $mysql_vacation = 'vacation';

   // the MySQL field that contains users' vacation text
   $mysql_vacation_text = 'vacation_text';
?>
