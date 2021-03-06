### Let build an e-email server!

Iris is a CGI script, Exim MTA and Dovecot configuration files, Vagrant and Ansible playbook, supplemented with instructions to build an e-mail server with virtual domains support, authenticated SMTP relay, vacation, SMTP-time malware/spam/over-quota reject, and web based account and domain administration, including domain-level access control for delegated domain management. Based on Exim MTA, Dovecot IMAP server, MySQL, Perl, Clamav, SpamAssassin, Roundcube webmail.

#### 1. Features

- Single server in this configuration is able to handle multiple independent domains with separate sets of users and aliases.
- Accounts maintenance is performed via web interface.
- Super-user(s) can modify everything. Selected users are allowed to modify domain(s) assigned to them, within limits set by configured quota.
- Malware is stopped at SMTP time by rejecting delivery instantly, the decisions are made by antivirus and antispam software, together with RBL.
- Accounts are monitored for space usage and e-mail delivery is deferred in case of over-quota condition.
- Vacation auto-responder is careful to whom and when it sends replies to and is end-user controllable via Roundcube webmail vacation plug-in.
- IMAP/POP3 logins could be disabled for selected domain, but preserving accounts and uninterrupted incoming message delivery.
- In preparation to move particular e-mail domain to the server, the domain could be hidden from MTA, and then made visible on the flip of a switch, after initial configuration is performed.

The system is used in a medium size installation, 1000+ active e-mail
accounts - and proven to be reliable, low TCO solution.


#### 2. System components

- [Exim MTA](http://www.exim.org/).
- [Dovecot IMAP](http://www.dovecot.org/) server.
- [MySQL](http://www.mysql.com/) database.
- Any webserver with CGI support. SSL is recommended for security.
- Perl and some additional modules from [CPAN](http://www.cpan.org/).
- Optionally, [ClamAV](http://www.clamav.net/) antivirus
  and [SpamAssassin](http://spamassassin.apache.org/) antispam filter.

Tested with Exim 4.x, Dovecot 2.2, MySQL 5.5, Apache 2.2, Nginx.


#### 3. Limitations

- DNS setup is not discussed here and is a separate task.
- This is not an out-of-the-box software, you need a basic understanding how underlying components works: Exim, MySQL, etc., to be able to polish the install. Yet the supplied Ansible playbook will give you a ready to use FreeBSD based system.
- Webmail is provisioned by Ansible, but it's setup is not described here.
- All information about the domain, its accounts and aliases is presented on one web page. This behavior simplifies programming and optimized for small to medium number of accounts in domain.


#### 4. Upgrading

For additional instructions specific to upgrading to current version see
[UPGRADE](https://bitbucket.org/arkadi/iris/src/tip/UPGRADE) document.


#### 5. Installation approaches

There are two alternatives:

- manual installation (described in details below, long and tedious);
- installation using Vagrant and Ansible to create complete VM.

As for the later: install Vagrant, Ansible, VirtualBox. Execute in current directory (iris/)

    $ vagrant up --provision

to download base-box (a Vagrant name for minimal prepared VM image), and provision it with Ansible. The `portsnap` stage is a little bit slow, but this installation must build some ports with specific features. Server SSL certificate CN and passwords are setup in `provision/playbook.yml`.

After provisioning procedure successfully completes, please restart the VM with

    $ vagrant reload

to apply new kernel parameters and start all services.
Open https://192.168.33.10/rc/installer/ in browser to initialize Roundcube database via Roundcube's Installer wizard.

After webmail is configured, ssh to the box and disable installer:

    $ vagrant ssh
    vagrant@box $ sudo chmod 0700 /www/mailhub.domain.com/rc/installer

Mail administration panel is at https://192.168.33.10/control-panel/ and user/pass is admin/superuserpassword. Webmail is at https://192.168.33.10/rc/.
Connect your IMAP client to 192.168.33.10:993.

Below are manual installation instructions.
If the instructions are unclear, then take a look at `provision/playbook.yml`.


#### 6. MySQL setup

Create database to be used for e-mail accounts information:

    mysql> create database mail default character set utf8;

Create two database users - one with SELECT right for Exim and Dovecot, and another one with SELECT, INSERT, UPDATE, and DELETE rights for `iris.cgi` and qwatch.pl`:

    mysql> grant select on mail.* to mail@localhost identified by 'password1';
    mysql> grant insert on mail.greylist to mail@localhost;
    -- for Dovecot expires plug-in
    mysql> grant select,insert,update on mail.expires to mail@localhost;
    mysql> grant select,insert,update,delete on mail.*
            to iris@localhost identified by 'password2';

Create tables and initial superuser account by executing `iris.sql` via `mysql`:

    $ mysql mail < iris.sql


#### 7. SSL

Create self-signed SSL certificate:

    $ openssl req -new -nodes -x509 \
        -subj "/C=US/ST=Oregon/L=Portland/O=IT/CN=mailhub.domain.com" \
        -days 5000 -keyout /usr/local/etc/mail.key -out /usr/local/etc/mail.crt \
        -extensions v3_ca


#### 8. Exim configuration

Supplied `exim.conf` should be a good start for your setup.

You need to create a number of (empty) list files in exim config `tabs/` directory.

    $ cd /usr/local/etc/exim
    $ touch aliases.global && mkdir aliases tabs && cd tabs &&
        touch host-reject ignore-dnsbl-hosts local-domains relay-domains relay-from-hosts

Note, that `vacation_reply` transport needs a directory to store history database and the transport `user` (smmsp) must differs from `exim_user` (mailnull):

    $ mkdir /var/spool/exim/vacation &&
      chown smmsp:mailnull /var/spool/exim/vacation &&
      chmod 2775 /var/spool/exim/vacation

Setup a cron job to purge old database files:
    
    $ crontab -e -u mailnull
    2 1 */10 * * find /var/spool/exim/vacation -mtime +30 -print0 | xargs -0 rm

(add -r to `xargs` on Linux)

Setup root crontab to expiry greylist entries, expunge Trash-es, rotate logs,
and sync time:

    $ crontab -e -u root
    3 1 * * * /usr/local/bin/mysql -e 'delete from mail.greylist where record_expires < now();'
    4 1 * * * /usr/local/bin/doveadm expunge -A mailbox Trash savedbefore 30d
    5 1 * * * /usr/local/bin/doveadm expunge -A mailbox Spam  savedbefore 30d
    6 1 * * * /usr/local/bin/doveadm expunge -A mailbox Junk  savedbefore 30d
    7 1 * * 7 /usr/local/sbin/exicyclog
    8 1 * * * /usr/sbin/ntpdate pool.ntp.org >/dev/null

Note, in case Courier IMAP compatible namespace is enabled in `dovecot.conf` via `namespace { prefix = INBOX. ... }` then you must reference the mailboxes with INBOX prefix. Ie. `doveadm expunge -A mailbox INBOX.Trash savedbefore 30d`.

#### 9. IMAP setup

Supplied dovecot*.conf files should be a good start for your setup.


#### 10. Perl setup

Install additional modules:

- CGI::Lite
- DBI
- DBD::mysql
- Digest::HMAC_MD5

FreeBSD has all necessary packages in ports:

    $ pkg install p5-CGI-Lite p5-DBD-mysql p5-Digest-HMAC


#### 11. iris.cgi and webserver configuration

Edit `iris.cgi` and change configuration variables. Probably change `$html_start` to use different CSS and `<title>`.

Place `iris.cgi` in cgi-bin directory. CGI must execute with `dovecot` UID to be able to create and remove maildir directories when account is deleted. For Apache 2.2 add to config:

    SuexecUserGroup dovecot dovecot
    <Directory /srv/http/iris>
        Options ExecCGI
        AddHandler cgi-script .cgi
        SSLOptions +StdEnvVars
        DirectoryIndex iris.cgi
    </Directory>

For Nginx add to config:

    location /iris {
        index index.cgi;
        location ~ \.cgi$ {
            fastcgi_pass unix:/tmp/cgi.sock;
        }
    }

Install `fcgiwrap`, start `iris.cgi`:

    env - LC_CTYPE=en_US.UTF-8 PATH=/none FCGI_WEB_SERVER_ADDRS=127.0.0.1 \
      /usr/local/bin/spawn-fcgi -M 0770 -u dovecot -g dovecot \
      -f '/usr/local/sbin/fcgiwrap -c 3' -s /tmp/cgi.sock \
      >> /var/log/nginx/error.log 2>&1
    chown :www /tmp/cgi.sock

Optionally configure SSL in webserver.


#### 12. iris.cgi - admin web interface

1. Point your browser to `iris.cgi` location and login with e-mail/pass: admin/superuserpassword. The account you just logged in is an initial superuser account.
2. Create and delete domain by entering its name in textbox and pressing appropriate action button.
3. To manage domain select domain name in listbox and press _Show_.
4. Every button on domain administration page work with corresponding section only. For example, you can't create and delete accounts in one step.
5. Domain level settings allows you to change default authenticated SMTP relay policy for new accounts, to disable clients logins, and to hide the domain from MTA.
6. To create account, enter information in following format:

    ```
    account[,QuotaMB,FirstName,Surname,phone#,other email,other info]
    ```

    For example:

    `john`, `jerry,20`, `someone,25,Some,One,+1 9xxx,secret@email.com,bla-bla-bla goes here comma,allowed`, `sparse,,,1234,,allowed too`.

    Default quota is defined in `iris.cgi`.

7. _Create Aliases_ works similarly. Format:

    ```
    alias aliased,to,..
    ```

    `alias` should be name without domain. `aliased,to` is email list. Name without domain part in `aliased,to` list means user in the same domain, like traditional `/etc/aliases` file `user1@domain2.com,user -> user1@domain2.com, user@domain.com`.

8. To update or delete accounts enter new info or check a checkbox, then press _Update_. You can update and delete multiple accounts in one step.
9. _Toggle SMTP_ checkbox toggles authenticated SMTP relay for particular acount, ie. if it is disabled it will be enabled, if it is enabled it will be disabled.
10. _Toggle AV_ checkbox disable or enable anti-virus and anti-spam filtering for account. AV filtering will be skipped if incoming mail has only one recipient with this flag set and no aliases expansion occurred before delivery.
11. _Aliases_ section works in similar way.
12. To edit vacation settings click on account name. When you change vacation status between off and custom, then custom text is preserved, but the text is erased if vacation is set to default text. Vacation message is UTF-8 clean.
13. To delegate domain management to the user, enter the list of managed domains into text area and set the quota. The quota will be shared across the specified domains and its usage will be updated even in case changes are made by other administrators or superusers. Only superuser can assign administrative rights.
14. _IMAP quota_ column may differs from _Quota_ because maildir quota may lag behind real (database stored) quota. Maildir quota is updated by Exim at delivery time.
15. _Inbox modified_ column shows the date when MUA modified the Inbox folder. Technically, it is a modification time of `maildir/cur/` directory.
16. It is recommended to create a real domain and e-email account for superuser and delete initial superuser account and domain. At least change the password. As a security measure, assignment of superuser rights to an account is only possible via mysql command line:

    ```
    mysql> update accounts set superuser = 1 where account = 'account@name.here';
    ```

#### 13. qwatch.pl - maildir over-quota monitor

If you want messages to over-quota mailboxes to be rejected at SMTP time you should run `qwatch.pl`. Edit the script to change configuration and run it under `dovecot` user:

    $ su -m dovecot -c '/usr/local/sbin/qwatch.pl &'

At start it will read the state from MySQL database, re-check the state of previously over-quota mailboxes, then it will run an infinite loop, periodically polling Exim main logfile for maildir over-quota messages, updating MySQL `accounts.overquota` flag and checking reported mailboxes to be still over-quota. Log file will be reopened when rotation is detected. Additionally, it monitors log file for peers that repeatedly hammers the server with messages larger than Exim `message_size_limit` (broken MUAs like Outlook) and updates the database to disable authenticated SMTP for them. This is a DoS potentially, so you can disable the functionality by commenting out `$too_big_str` configuration variable.

#### 14. Author and licensing

Arkadi Shishlov - arkadi.shishlov at gmail.com
The license is GPL v3.
