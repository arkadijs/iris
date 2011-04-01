<?php
	/* Until the email is set in SquirrelMail preferences it is 
	 * not possible to send email.
	 * Users rightfully expect it to work by default.
	 * Assume the user login name is email. 
	 */
    function squirrelmail_plugin_init_set_email() {
       global $squirrelmail_plugin_hooks;

       $squirrelmail_plugin_hooks['loading_prefs']['set_email'] = 'set_email_address';
    }

    function set_email_address() {
        global $data_dir, $username;

        if (isset($username) && !empty($username)) {
            $email_address = getPref($data_dir, $username, 'email_address');
            if (empty($email_address)) {
                setPref($data_dir, $username, 'email_address', $username);
              //setPref($data_dir, $username, 'language', 'lv_LV'); // choose UTF-8 as default charset
            }
        }
    }
?>
