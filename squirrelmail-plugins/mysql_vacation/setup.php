<?php

function squirrelmail_plugin_init_mysql_vacation()
{
    global $squirrelmail_plugin_hooks;
    $squirrelmail_plugin_hooks['optpage_register_block']['mysql_vacation'] = 'mysql_vacation_opt';
}

function mysql_vacation_opt()
{
    global $optpage_blocks;

    $optpage_blocks[] = array(
        'name' => _("Vacation / Autoresponder"),
        'url' => '../plugins/mysql_vacation/options.php',
        'desc' => _("Set up an auto-reply message for your incoming email. This can be useful when you are away on vacation."),
        'js' => FALSE
    );
}

function mysql_vacation_version()
{
   return '0.6';
}
?>
