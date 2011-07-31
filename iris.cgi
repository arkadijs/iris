#!/usr/bin/perl -Tw

# version 0.6.2

# the inactivity period in seconds after which user must re-authenticate
my $inactivity_period = 1200;
# the IPs the superuser privileged accounts can login from
# just leave the list empty to disable the check
my @superuser_allowed_ip;
@superuser_allowed_ip = qw(192.168.1.5 10.0.20.40);
my $mysql_host = 'localhost;mysql_socket=/tmp/mysql.sock41';
my $mysql_db   = 'mail';
my $mysql_user = 'iris';
my $mysql_pwd  = 'password2';
my $imap_spool = '/var/imap';
my $imap_default_quota = 50; # MB
my $imap_pwd_len = 8;
# generate pretty passwords 0/1
my $pretty_pw  = 1;
# uncomment if you want to use random device
# used when pretty_pw is 0
# use Urandom only - non-blocking random device
my $dev_random = '/dev/urandom';
# when set to 1 the newly created domain is hidden from MTA
# until "normal delivery" is enabled via web panel
my $domain_is_non_local_by_default = 0;
# send welcome mail to create mbox and set maildir quota
# if set to 0 then maildirmake will be used to create mailbox
my $send_welcome_mail = 1;
# or /bin/mail
my $bin_mail   = '/usr/bin/mail';
# sendmail is preferred method in case message is in utf-8
my $sendmail   = '/usr/sbin/sendmail';
# maildirmake is a must when $send_welcome_mail = 0
# and strongly recommended in case you want to create accounts
# when domain has non-local delivery mode set  
# otherwise mailbox will be created by first production email;
# depending on IMAP server, the absence of IMAP folder most likely
# results a MUA login failure until then
my $maildirmk;
$maildirmk     = '/usr/local/bin/maildirmake';
# used to recursively remove imap account maildir folder
my $bin_rm     = '/bin/rm';
# syslog facility
my $syslog_facility = 'mail';
# use UNIX socket to connect to syslog, 1 or 0
my $syslog_unix = 1;
my $welcome_subj = 'Test message';
my $welcome_text =
"I'm just a test message sent to you to confirm your account is working properly.
It is safe to delete me.
";
my $welcome_email_headers =
"From: info\@domain.com
To: \$email_to
Subject: $welcome_subj
MIME-Version: 1.0
Content-Type: text/plain; charset=utf-8
Content-Transfer-Encoding: 8bit";
# display column headers every N rows in account list
my $acc_hdr_row_every = 25;
my $debug = 0;

# end of config

use strict;
use CGI::Lite;
use Digest::MD5 qw(md5_hex);
use Digest::HMAC_MD5 qw(hmac_md5_hex);
use DBI;
use IO::File;
use Sys::Syslog qw(:DEFAULT setlogsock);
eval 'use Data::Dumper;' if $debug;

$ENV{PATH} = '';
$ENV{HOME} = $imap_spool;

my $https = exists $ENV{'HTTPS'};
my $me = my_base_url();
my $client_ip = $ENV{'REMOTE_ADDR'};
my $now = time();

# templates

my $html_start = <<EOF
<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">
<html>
<head>
  <title>mail</title>
  <style type="text/css">
  <!--
  strong       { font-weight: bold; }
  .attention   { color: red; }
  textarea     { width: 90%; height: 10em; }
  table        { width: 100%; border: thin blue solid; }
  table.small  { width: auto; border: none; }
  hr           { width: 100%; }
  tr.even      { }
  tr.odd       { background-color: Lavender;  }
  td.lheader   { font-weight: bold; }
  td.header    { font-weight: bold; height: 2em; }
  td.hdrcntr   { font-weight: bold; height: 2em; text-align: center; }
  td.datcntr   { text-align: center; }
  td.datup     { vertical-align: top; }
  td.datupcntr { vertical-align: top; text-align: center; }
  td.datright  { text-align: right; }
  input.login_creds    { width: 12em; }
  input.button         { width: 7em; }
  input.buttonw        { width: 9em; }
  input.domain_name    { width: 10em; }
  input.new_quota      { width: 5em; }
  input.new_passwd     { width: 6em; }
  input.new_aliased_to { width: 20em; }
  -->
  </style>
</head>
<body>
<span style="float: right;">
\$logout
\$user_info
</span>
EOF
;

my $html_login_form = <<EOF
<center>
<form action="$me" method="POST">
<table class="small">
  <tbody>
  <tr>
    <td class="datright">E-mail:</td>
    <td><input type="text" class="login_creds" name="login_username" value="\$login_username"></td>
  </tr>
  <tr>
    <td class="datright">Password:</td>
    <td><input type="password" class="login_creds" name="login_password"></td>
  </tr>
  <tr>
    <td></td>
    <td><input type="submit" class="button" name="login_action" value="Login"></td>
  </tr>
  </tbody>
</table>
</form>
</center>
EOF
;

my $html_logout_link = <<EOF
<a href="$me?logout">Logout</a>
EOF
;

my $html_user_info = <<EOF
\$info
EOF
;

my $html_login_bad_auth = <<EOF
<strong>E-mail and password does not match</strong>
EOF
;

my $html_logged_out = <<EOF
<strong>You've been successfully logged out. Please login <a href="$me">here</a>.</strong>
EOF
;

my $html_nothing_to_manage = <<EOF
<strong>There is nothing to manage</strong>
EOF
;

my $html_no_access = <<EOF
<br><strong>Permission denied</strong>
EOF
;

my $html_over_accounts_quota = <<EOF
<br><strong>You're over your account quota</strong>
EOF
;

my $html_over_space_quota = <<EOF
<br><strong>You're over your space quota</strong>
EOF
;

my $html_bad_quota_format = <<EOF
<br><strong>Bad quota value, assumed default quota of ${imap_default_quota}MB:</strong>
EOF
;

my $html_hr = <<EOF
<hr>
EOF
;

my $html_domains_superuser = <<EOF
<strong>Domains</strong><br>
<form action="$me" method="POST">
<table style="margin-top: 0.5em">
  <tbody>
  <tr>
    <td>
      <select name="select_domain">
      \$domain_list
      </select>
      <input type="submit" class="button" name="domain_action" value="Show">
    </td>
    <td align="right"><input type="text"   class="domain_name" name="text_domain"></td>
    <td>              <input type="submit" class="button"      name="domain_action" value="Create">
                      <input type="submit" class="button"      name="domain_action" value="Remove"></td>
    <td align="right"><input type="submit" class="buttonw"     name="list_overquota" value="List Overquota"></td>
  </tr>
  </tbody>
</table>
</form>
EOF
;

my $html_domains_delegated = <<EOF
<form action="$me" method="POST">
  <select name="select_domain">
    \$domain_list
  </select>
  <input type="submit" class="button" name="domain_action" value="Show">
</form>
EOF
;

my $html_domains_single = <<EOF
<strong><a href="$me?domain=\$domain&domain_action=Show">\$domain</a></strong><br>
EOF
;

my $html_domain = <<EOF
<strong>\$domain</strong>
<form action="$me" method="POST">
<table class="small">
  <tbody>
    <tr><td class="datright">Accounts:</td>
        <td>\$account_count</td></tr>
    <tr><td class="datright">Aliases:</td>
        <td>\$alias_count</td></tr>
    <tr><td class="datright">Quota used:</td>
        <td>\$quota_used</td></tr>
    <tr><td class="datright">Quota allocated:</td>
        <td>\$quota_allocated</td></tr>
    \$html_domain_superuser_admins
    <tr><td class="datright">Authenticated SMTP by default</td>
        <td><input type="radio" name="domain_smtp_auth_default" value="on" \$smtp_chk_on>enabled (for new accounts)</td></tr>
    <tr><td></td>
        <td><input type="radio" name="domain_smtp_auth_default" value="off" \$smtp_chk_off>disabled</td></tr>
    \$html_domain_superuser_settings
  </tbody>
</table>
<br>
<input type="hidden" name="domain" value="\$domain">
<input type="submit" class="button" name="domain_action" value="Update">
</form>
EOF
;

my $html_domain_superuser_admins = <<EOF
    <tr><td class="datright">Administrators:</td>
        <td>\$domain_admins</td></tr>
EOF
;

my $html_domain_superuser_settings = <<EOF
    <tr><td class="datright">IMAP/POP3 login</td>
        <td><input type="radio" name="domain_imap_login" value="on" \$imap_chk_on>enabled</td></tr>
    <tr><td></td>
        <td><input type="radio" name="domain_imap_login" value="off" \$imap_chk_off>disabled</td></tr>
    <tr><td class="datright">Domain is</td>
        <td><input type="radio" name="domain_non_local" value="off" \$local_chk_on>local (normal delivery)</td></tr>
    <tr><td></td>
        <td><input type="radio" name="domain_non_local" value="on" \$local_chk_off>non-local</td></tr>
EOF
;

my $html_accounts = <<EOF
<strong>\$domain Accounts</strong><br>
<form action="$me" method="POST">
<table class="accounts">
  <tbody>
    \$account_list
  </tbody>
</table>
<br>
<input type="hidden" name="domain" value="\$domain">
<input type="submit" class="button" name="update_accounts" value="Update">
</form>
EOF
;

my $html_account_hdr_row = <<EOF
    <tr>
       <td class="header">Account        </td>
       <td class="header">Used           </td>
       <td class="header">Quota          </td>
       <td class="header">IMAP Quota     </td>
       <td class="header">Inbox modified </td>
       <td class="hdrcntr">New Quota (MB)</td>
       <td class="hdrcntr">SMTP Allowed? </td>
       <td class="hdrcntr">Toggle SMTP   </td>
       <td class="hdrcntr">AV Disabled?  </td>
       <td class="hdrcntr">Toggle AV     </td>
       <td class="hdrcntr">Vacation?     </td>
       <td class="hdrcntr">New Password  </td>
       <td class="hdrcntr">Delete        </td>
    </tr>
EOF
;

my $html_account_row = <<EOF
    <tr class="\$row_class">
      <td><a href="\$account_edit_link">\$local_part</a></td>
      <td>\$quota_used</td>
      <td>\$quota     </td>
      <td>\$quota_imap</td>
      <td>\$imap_modified</td>
      <td class="datcntr"><input type="text" class="new_quota"  name="new_quota_\$id">        </td>
      <td class="datcntr">\$smtp_auth</td>
      <td class="datcntr"><input type="checkbox"                name="smtp_auth" value="\$id"></td>
      <td class="datcntr"><span class="attention">\$av_disabled</span></td>
      <td class="datcntr"><input type="checkbox"                name="av_toggle" value="\$id"></td>
      <td class="datcntr">\$vacation</td>
      <td class="datcntr"><input type="text" class="new_passwd" name="new_passwd_\$id">       </td>
      <td class="datcntr"><input type="checkbox"                name="delete"    value="\$id"></td>
    </tr>
EOF
;

my $html_edit_account = <<EOF
<strong>\$account</strong><br>
<form action="$me" method="POST">
    <input type="radio" name="vacation_\$id" value="off"     \$chk_off>  Vacation disabled<br>
    <input type="radio" name="vacation_\$id" value="default" \$chk_def>  Vacation enabled with standard reply text<br>
    <input type="radio" name="vacation_\$id" value="custom"  \$chk_cust> Vacation enabled with custom reply text:<br>
<textarea name="vacation_custom_text_\$id">\$vacation_custom_text</textarea><br>
\$superuser_account_actions
<input type="hidden" name="domain" value="\$domain">
<input type="submit" class="button" name="update_accounts" value="Update">
</form>
EOF
;

my $html_edit_account_superuser_only = <<EOF
<hr>
<strong>Managed domains (one per line)</strong><br>
<textarea name="managed_domains_\$id">\$managed_domains</textarea>
<table class="small">
  <tbody>
    <tr>
      <td></td>
      <td class="header">Allocated</td>
      <td class="header">Quota</td>
      <td class="header">New quota</td>
    </tr>
    <tr>
      <td class="lheader">Space (MB)</td>
      <td>\$admin_quota</td>
      <td>\$admin_max_quota</td>
      <td><input type="text" class="new_quota" name="new_admin_max_quota_\$id"></td>
    </tr>
    <tr>
      <td class="lheader">Accounts+aliases&nbsp;&nbsp;</td>
      <td>\$admin_accounts</td>
      <td>\$admin_max_accounts</td>
      <td><input type="text" class="new_quota" name="new_admin_max_accounts_\$id"></td>
    </tr>
  </tbody>
</table>
<!-- input type="checkbox" name="recalc_admin_account_used" value="\$id"> Recalculate quota usage -->
<br>
EOF
;

my $html_create_accounts = <<EOF
<strong>Create New Accounts in \$domain Domain</strong><br>
account[,QuotaMB(default ${imap_default_quota}MB),FirstName,Surname,phone,other email,other info]<br>
<form action="$me" method="POST">
<textarea name="new_accounts">
</textarea>
<br>
<input type="hidden" name="domain" value="\$domain">
<input type="submit" class="button" name="create_accounts" value="Create">
</form>
EOF
;

my $html_aliases = <<EOF
<strong>\$domain Aliases</strong><br>
<form action="$me" method="POST">
<table>
  <tbody>
    <tr>
      <td class="header">Alias         </td>
      <td class="header">Aliased To    </td>
      <td class="header">New Aliased To</td>
      <td class="hdrcntr">Delete       </td>
    </tr>
    \$alias_list
  </tbody>
</table>
<br>
<input type="hidden" name="domain" value="\$domain">
<input type="submit" class="button" name="update_aliases" value="Update">
</form>
EOF
;

my $html_alias_row = <<EOF
    <tr class="\$row_class">
      <td class="datup">\$local_part</td>
      <td class="datup">\$aliased_to</td>
      <td class="datup"><input type="text" class="new_aliased_to" name="new_aliased_to_\$id"></td>
      <td class="datupcntr"><input type="checkbox"    name="delete" value="\$id"></td>
    </tr>
EOF
;

my $html_create_aliases = <<EOF
<strong>Create New Aliases in \$domain Domain</strong><br>
alias aliased,to<br>
<form action="$me" method="POST">
<textarea name="new_aliases">
</textarea>
<br>
<input type="hidden" name="domain" value="\$domain">
<input type="submit" class="button" name="create_aliases" value="Create">
</form>
EOF
;

my $html_overquota_form = <<EOF
<strong>Overquota Accounts</strong><br>
<form name="overquotalist" action="$me" method="POST">
<table class="accounts">
  <tbody>
    <tr>
       <td class="header">Account</td>
       <td class="header">Quota  </td>
       <td class="header">Used   </td>
       <td class="header">Inbox modified</td>
    </tr>
    \$overquota_accounts
  </tbody>
</table>
<input type="hidden" name="text_domain"   value="">
<input type="hidden" name="domain_action" value="Show">
</form>
EOF
;

my $html_overquota_row = <<EOF
    <tr>
      <td><a href="$me?domain=\$domain&domain_action=Show">\$account</a></td>
      <td>\$quota     </td>
      <td>\$quota_used</td>
      <td>\$imap_modified</td>
    </tr>
EOF
;

my $html_end = <<EOF
</body>
</html>
EOF
;

# code

my $cgi;
my $mysql;
my ($user, $user_id, $superuser, $managed_domains, $admin_quota, $admin_accounts, $admin_max_quota, $admin_max_accounts);

sub mysql_connect {
    return if defined $mysql;
    $mysql = DBI->connect("dbi:mysql:dbname=$mysql_db;host=$mysql_host",
                 $mysql_user, $mysql_pwd)
        || error("Could not connect to MySQL server");
    mysql_do("set names utf8");
}

# execute statement with bind variables
# exit CGI on failure
sub mysql_do {
    my ($sql, @bind_values) = @_;
    my $stm = $mysql->prepare($sql)
        || error("MySQL prepare($sql) failed: ". $mysql->errstr);
    $stm->execute(@bind_values)
        || error("MySQL execute($sql) failed: ". $mysql->errstr);
    return $stm;
}

# execute select statement and fetch exectly one row
# exit on failure or row count != 1
sub mysql_single_row {
    my $sel = mysql_do(@_);
    my @row;
    if (!(@row = $sel->fetchrow_array())) {
        error("MySQL returned no rows ($_[0]): ". $mysql->errstr);
    }
    if ($sel->fetchrow_array()) {
        error("MySQL returned more than one row ($_[0])");
    }
    return @row;
}

sub verify_login_credentials {
    my ($account, $password) = @_;
    my ($c) = mysql_single_row("select count(1) from accounts where account = ? and pwd = ?", $account, $password);
    return 0 if !$c;
    if (@superuser_allowed_ip) {
        my ($super) = mysql_single_row("select superuser from accounts where account = ? and pwd = ?", $account, $password);
        if ($super) {
            foreach my $ip (@superuser_allowed_ip) {
                if ($ip eq $client_ip) {
                    return 1;
                }
            }
            return 0;
        }
    }
    return 1;
}

# get quota out of maildirsize file
sub imap_info {
    my $mbox = shift;
    my $mdirsz = $imap_spool .'/'. $mbox .'/maildirsize';
    open(S, "< $mdirsz") || return (0, 0);
   #open(S, "< $mdirsz") || error("open($mdirsz) failed: $!");
    my $first_line = <S>;
    my ($quota) = $first_line =~ /(\d+)S/i;
    return (0, 0) unless defined $quota;
    my $quota_used = 0;
    while (<S>) {
        $quota_used += (split)[0];
    }
    close(S);
    # sometimes it happens
    $quota_used = 0 if $quota_used < 0;
    my $imap_modified = (stat($imap_spool .'/'. $mbox .'/cur'))[9]; # mtime
    return ($quota, $quota_used, $imap_modified);
}

# convert to human readable format
# append MB or KB
sub int2kib {
    my $b = shift;
    my $k = 1024;
    my $m = 1024*1024;
    my $g = 1024*1024*1024;
    my $r;
    $r = $b/$g; return sprintf("%.1f", $r) .'GB' if $r >= 1;
    $r = $b/$m; return int($r) .'MB' if $r >= 1;
    $r = $b/$k; return int($r) .'KB' if $r >= 1;
    return $b;
}

# returns time for today's dates, yyyy.mm.dd otherwise
sub sec2date {
	my $d = shift;
	return '' unless defined $d;
    my ($sec, $min, $hour, $day, $mon, $year) = localtime($d);	
	if ($now - $d < 24*60*60) { # today
		return sprintf("%02d:%02d", $hour, $min);
	} else {
        return sprintf("%4d.%02d.%02d", $year+1900, $mon+1, $day);
	}
}

# accounts in particular domain
sub account_list {
    my @accounts;
    my $domain = shift;
    my $sel = mysql_do(
        "select id,
                local_part,
                if(smtp_auth,   'Y', '') smtp_auth,
                if(av_disabled, 'Y', '') av_disabled,
                if(vacation,    'Y', '') vacation,
                quota*1024*1024 quota
           from accounts
          where domain = ?
          order by local_part", $domain);
    while (my $_row = $sel->fetchrow_hashref()) {
        my %row = %$_row;
        my @q = imap_info($row{local_part} .'@'. $domain);
        $row{quota_imap} = $q[0];
        $row{quota_used} = $q[1];
        $row{imap_modified} = $q[2];
        push @accounts, { %row };
    }
    return \@accounts;
}

# aliases in particular domain
sub alias_list {
    my @aliases;
    my $domain = shift;
    my $sel = mysql_do("select id, local_part, aliased_to from aliases where domain = ? order by local_part", $domain);
    while (my $_row = $sel->fetchrow_hashref()) {
        my %row = %$_row;
        $row{aliased_to} =~ s/\@\Q$domain\E//go;
        push @aliases, { %row };
    }
    return \@aliases;
}

sub domain_exists {
    my $domain = shift;
    my ($c) = mysql_single_row("select count(1) from domains where domain = ?", $domain);
    return $c;
}

sub create_domain {
    my $domain = shift;
    print $html_hr;
    if (domain_exists($domain)) {
        print "<br><strong>Domain $domain already exist</strong>\n";
        return;
    }
    mysql_do("insert into domains (domain, non_local) values (?, ?)", $domain, $domain_is_non_local_by_default);
    print "<br><strong>Domain $domain created</strong>\n";
    print "<br><a href=\"$me\">refresh domain list</a>\n";
}

sub delete_domain {
    my $domain = shift;
    print $html_hr;
    if (!domain_exists($domain)) {
        print "<br><strong>Domain $domain does not exist</strong>\n";
        return;
    }
    my ($c) = mysql_single_row("select count(1) from accounts where domain = ?", $domain);
    my ($a) = mysql_single_row("select count(1) from aliases where domain = ?", $domain);
    if ($c > 0 || $a > 0) {
        print "<br><strong>Domain $domain still have accounts and/or aliases, cannot delete</strong>\n";
    } else {
        mysql_do("delete from domains where domain = ?", $domain);
        print "<br><strong>Domain $domain removed</strong>\n";
        print "<br><a href=\"$me\">refresh domain list</a>\n";
    }
}

sub get_domain_settings {
    my $domain = shift;
    return mysql_single_row("select smtp_auth, non_local from domains where domain = ?", $domain);
}

my $account_count = 0;
my $alias_count = 0;
my $domain_quota_used = 0;
my $domain_quota_allocated = 0;

sub radio_checked {
    my $c = 'checked';
    return (shift) ? ($c, '') : ('', $c);
}

sub show_domain {
    my $domain = shift;
    my ($imap_disabled, $non_local, $smtp_auth_default) =
        mysql_single_row("select disabled, non_local, smtp_auth from domains where domain = ?", $domain);
    print $html_hr;
    my ($smtp_chk_on, $smtp_chk_off) = radio_checked($smtp_auth_default);
    $html_domain =~ s/\$domain/$domain/g;
    $html_domain =~ s/\$account_count/$account_count/g;
    $html_domain =~ s/\$alias_count/$alias_count/g;
    $domain_quota_used = int2kib($domain_quota_used);
    $domain_quota_allocated = int2kib($domain_quota_allocated);
    $html_domain =~ s/\$quota_used/$domain_quota_used/g;
    $html_domain =~ s/\$quota_allocated/$domain_quota_allocated/g;
    $html_domain =~ s/\$smtp_chk_on/$smtp_chk_on/g;
    $html_domain =~ s/\$smtp_chk_off/$smtp_chk_off/g;

    if (!$superuser) {
        $html_domain =~ s/\$html_domain_superuser_(?:admins|settings)//g;
    } else {
        my $domain_admins = mysql_do(
            "select id, account from accounts where id in (select acc_id from managed_domains where dom_id = ?) order by account",
            $managed_domains->{$domain})->fetchall_arrayref();
        my $admins = 'none';
        if (@$domain_admins) {
            $admins = join("&nbsp;&nbsp;", map {
                    "<a href=\"$me?edit_account=$_->[0]&domain=$domain\">$_->[1]</a>"
                } @$domain_admins);
        }
        $html_domain_superuser_admins =~ s/\$domain_admins/$admins/;
        $html_domain =~ s/\$html_domain_superuser_admins/$html_domain_superuser_admins/;
        my ($imap_chk_on, $imap_chk_off) = radio_checked(!$imap_disabled);
        my ($local_chk_on, $local_chk_off) = radio_checked(!$non_local);
        $html_domain_superuser_settings =~ s/\$imap_chk_on/$imap_chk_on/;
        $html_domain_superuser_settings =~ s/\$imap_chk_off/$imap_chk_off/;
        $html_domain_superuser_settings =~ s/\$local_chk_on/$local_chk_on/;
        $html_domain_superuser_settings =~ s/\$local_chk_off/$local_chk_off/;
        $html_domain =~ s/\$html_domain_superuser_settings/$html_domain_superuser_settings/;
    }
    print $html_domain;
}

sub update_domain {
    my $c = shift;
    my $domain = $c->{domain};
    access($domain);

    my $smtp_auth = $c->{domain_smtp_auth_default} eq 'on' ? 1 : 0;
    if ($superuser) {
        my ($imap_disabled_in_db) = mysql_single_row("select disabled from domains where domain = ?", $domain);
        my $imap_disabled = $c->{domain_imap_login} eq 'off' ? 1 : 0;
        my $non_local =     $c->{domain_non_local}  eq 'on'  ? 1 : 0;
        mysql_do('update domains set smtp_auth = ?, disabled = ?, non_local = ? where domain = ?',
            $smtp_auth, $imap_disabled, $non_local, $domain);
        if ($imap_disabled_in_db != $imap_disabled) {
            mysql_do('update accounts set disabled = ? where domain = ?', $imap_disabled, $domain);
        }
    } else {
        mysql_do('update domains set smtp_auth = ? where domain = ?', $smtp_auth, $domain);
    }

    print "<br><strong>$domain Updated</strong>\n";
    print "<br><a href=\"$me?domain=$domain\">refresh domain list</a>\n" if $superuser;
}

my $account_list;
# output HTML table with all accounts in domain
sub prepare_show_accounts {
    my $domain = shift;
    my $account_list_ref = account_list($domain);
    $account_count = $#{$account_list_ref} + 1;
    if ($account_count > 0) {
        my $i = $acc_hdr_row_every;
        foreach my $r (sort { $a->{local_part} cmp $b->{local_part} } @{$account_list_ref}) {
            my $h = $html_account_row;
            $h =~ s/\$account_edit_link/${me}?edit_account=$r->{id}&domain=$domain/g;
            $h =~ s/\$local_part/$r->{local_part}/g;
            my $q;
            $q = int2kib($r->{quota_imap});
            $h =~ s/\$quota_imap/$q/g;
            $q = int2kib($r->{quota_used});
            $q = '<span class="attention">'. $q .'</span>' if $r->{quota_used} > $r->{quota};
            $h =~ s/\$quota_used/$q/g;
            $q = int2kib($r->{quota}); $h =~ s/\$quota/$q/g;
            $domain_quota_used += $r->{quota_used};
            $domain_quota_allocated += $r->{quota};
            $q = sec2date($r->{imap_modified});
            $h =~ s/\$imap_modified/$q/g;
            $h =~ s/\$smtp_auth/$r->{smtp_auth}/g;
            $h =~ s/\$av_disabled/$r->{av_disabled}/g;
            $h =~ s/\$vacation/$r->{vacation}/g;
            $h =~ s/\$id/$r->{id}/g;
            if ($i >= $acc_hdr_row_every) {
                $i = 0;
                $account_list .= $html_account_hdr_row;
            }
            my $row_class = ($i % 2) ? 'odd' : 'even';
            $h =~ s/\$row_class/$row_class/g;
            $account_list .= $h;
            ++$i;
        }
        $html_accounts =~ s/\$domain/$domain/g;
        $html_accounts =~ s/\$account_list/$account_list/g;
    }
}

sub show_accounts {
    if ($account_count > 0) {
        print $html_hr;
        print $html_accounts;
    }
}

# output HTML textarea for account creation
sub show_create_accounts {
    my $domain = shift;
    print $html_hr;
    $html_create_accounts =~ s/\$domain/$domain/g;
    print $html_create_accounts;
}

# output HTML table with all aliases in domain
sub prepare_show_aliases {
    my $domain = shift;
    my $alias_list_ref = alias_list($domain);
    $alias_count = $#{$alias_list_ref} + 1;
    if ($alias_count > 0) {
        my $i = 0;
        my $alias_list = join("\n", map {
            my $h = $html_alias_row;
            $h =~ s/\$local_part/$_->{local_part}/g;
            $_->{aliased_to} =~ s/,/, /g;
            $h =~ s/\$aliased_to/$_->{aliased_to}/g;
            $h =~ s/\$id/$_->{id}/g;
            my $row_class = ($i++ % 2) ? 'odd' : 'even';
            $h =~ s/\$row_class/$row_class/g;
            $h;
        } sort { $a->{local_part} cmp $b->{local_part} } @{$alias_list_ref});
        $html_aliases =~ s/\$domain/$domain/g;
        $html_aliases =~ s/\$alias_list/$alias_list/g;
    }
}

sub show_aliases {
    if ($alias_count > 0) {
        print $html_hr;
        print $html_aliases;
    }
}

# output HTML textarea for alias creation
sub show_create_aliases {
    my $domain = shift;
    print $html_hr;
    $html_create_aliases =~ s/\$domain/$domain/g;
    print $html_create_aliases;
}

# show account editor, setup variables usable by update_accounts()
# currently only settings that are not on main domain edit screen
sub account_editor {
    my $id = shift;
    my $chk = 'checked';
    my ($chk_off, $chk_def, $chk_cust) = ('', '', '');
    print $html_hr;
    my ($local_part, $domain, $vacation, $vacation_text, $u_admin_quota, $u_admin_accounts, $u_admin_max_quota, $u_admin_max_accounts) =
        mysql_single_row("select local_part, domain, vacation, vacation_text, admin_quota, admin_accounts, admin_max_quota, admin_max_accounts from accounts where id = ?", $id);
    access($domain);
    $vacation_text = '' if !defined $vacation_text;
    if ($vacation) {
        if (length($vacation_text) > 0) {
            $chk_cust = $chk;
        } else {
            $chk_def = $chk;
        }
    } else {
        $chk_off = $chk;
    }
    my $h = $html_edit_account;
    $h =~ s/\$account/$local_part\@$domain/g;
    $h =~ s/\$domain/$domain/g;
    $h =~ s/\$chk_off/$chk_off/g;
    $h =~ s/\$chk_def/$chk_def/g;
    $h =~ s/\$chk_cust/$chk_cust/g;
    $h =~ s/\$vacation_custom_text/$vacation_text/g;
    if ($superuser) {
    	my $hs = $html_edit_account_superuser_only;
        $hs =~ s/\$admin_quota/$u_admin_quota/;
        $hs =~ s/\$admin_accounts/$u_admin_accounts/;
        $hs =~ s/\$admin_max_quota/$u_admin_max_quota/;
        $hs =~ s/\$admin_max_accounts/$u_admin_max_accounts/;
        
        my $md = mysql_do(
            "select domain from domains where id in (select dom_id from managed_domains where acc_id = ?) order by domain",
            $id)->fetchall_arrayref();
        $md = join("\n", map { $_->[0] } @$md);
        $hs =~ s/\$managed_domains/$md/;

        $h =~ s/\$superuser_account_actions/$hs/;
    } else {
    	$h =~ s/\$superuser_account_actions//;
    }
    $h =~ s/\$id/$id/g;
    print $h;
}

# update accounts, use PK IDs from CGI POST data
sub update_accounts {
    my $c = shift;

    my @to_del;
    my @chsmtp;
    my @chav;
    my %chpwd;
    my %chquot;
    my %chvacation;
    my @recalc;
    my %chadmacc;
    my %chadmquot;
    my %chadmmng;

    print $html_hr;
    while (my ($k, $v) = each(%$c)) {
        next if $v eq '';
        if ($k eq 'delete') {
            @to_del = ref($v) eq 'ARRAY' ? @$v : $v;
        } elsif ($k eq 'smtp_auth') {
            @chsmtp = ref($v) eq 'ARRAY' ? @$v : $v;
        } elsif ($k eq 'av_toggle') {
            @chav = ref($v) eq 'ARRAY' ? @$v : $v;
        } elsif ($k =~ /^new_passwd_(\d+)$/) {
            $chpwd{$1} = $v;
        } elsif ($k =~ /^new_quota_(\d+)$/) {
            $chquot{$1} = $v;
        } elsif ($k =~ /^vacation_(\d+)$/) {
            $chvacation{$1} = [ $v, $c->{"vacation_custom_text_$1"} ];
            # XXX hack, because managed_domains is not set in request when list of domains is cleared completelly
            $chadmmng{$1} = ' ' if not exists $chadmmng{$1};
        } elsif ($superuser && $k eq 'recalc_admin_account_used') {
            @recalc = ref($v) eq 'ARRAY' ? @$v : $v;
        } elsif ($superuser && $k =~ /^new_admin_max_quota_(\d+)$/) {
            $chadmquot{$1} = $v;
        } elsif ($superuser && $k =~ /^new_admin_max_accounts_(\d+)$/) {
            $chadmacc{$1} = $v;
        } elsif ($superuser && $k =~ /^managed_domains_(\d+)$/) {
            $chadmmng{$1} = $v;
        } elsif ($k ne 'update_accounts' && $k ne 'domain' &&
                $k ne get_cookie_name() &&
                $k !~ /^vacation_custom_text_(?:\d+)$/) {
            # this might generate unecessary messages because of the foreign cookie for the same server
           #print "<strong><br>Unknown parameter for account update: $k</strong>";
        }
    }
   #print "\n<pre>\n";
   #print "to delete:\n";  print Dumper(\@to_del);
   #print "chpwd:\n";      print Dumper(\%chpwd);
   #print "chquot:\n";     print Dumper(\%chquot);
   #print "chvacation:\n"; print Dumper(\%chvacation);
   #print "chsmtp:\n";     print Dumper(\@chsmtp);
   #print "chav:\n";       print Dumper(\@chav);
   #print "\n</pre>\n";

    map { change_passwd($_, $chpwd{$_}) }        keys %chpwd;
    map { change_quota($_, $chquot{$_}) }        keys %chquot;
    map { change_vacation($_, $chvacation{$_}) } keys %chvacation;
    map { recalc_admin_account_used($_) }        @recalc;
    map { change_admin_max_quota($_, $chadmquot{$_}) } keys %chadmquot;
    map { change_admin_max_accounts($_, $chadmacc{$_}) } keys %chadmacc;
    map { change_admin_managed_domains($_, $chadmmng{$_}) } keys %chadmmng;
    map { change_smtp_auth($_) } @chsmtp;
    map { change_av($_)        } @chav;
    map { delete_account($_)   } @to_del;
    print "<br><strong>Account(s) Updated</strong>\n";
}

# delete account from MySQL and IMAP by ID
sub delete_account {
    my $id = shift;
    my ($local_part, $domain, $quota) =
        mysql_single_row('select local_part, domain, quota from accounts where id = ?', $id);
    access($domain);
    # XXX insert check deleted account == currently logged-in user?
    mysql_do('delete from managed_domains where acc_id = ?', $id);
    mysql_do('delete from accounts where id = ?', $id);
    mysql_do('update accounts set admin_accounts = admin_accounts - 1, admin_quota = admin_quota - ? where id in'.
        ' (select acc_id from managed_domains where dom_id = ?)', $quota, $managed_domains->{$domain});
    # XXX insert more safeguards?
    system($bin_rm, '-r', "$imap_spool/$local_part\@$domain");
    print "<br>$local_part\@$domain deleted\n";
    info("account deleted: $local_part\@$domain");
}

# change vacation settings by ID
sub change_vacation {
    my ($id, $v) = @_;
    my ($vacation, $vacation_text) = @$v;
    my ($local_part, $domain) =
        mysql_single_row('select local_part, domain from accounts where id = ?', $id);
    access($domain);
    if ($vacation eq 'off') {
        $vacation = undef;
    } elsif ($vacation eq 'default') {
        $vacation = 1;
        $vacation_text = undef;
    } elsif ($vacation eq 'custom') {
        $vacation = 1;
    } else {
        error("Unknown vacation setting value: \"$vacation\"");
    }
    mysql_do('update accounts set vacation = ?, vacation_text = ? where id = ?',
        $vacation, $vacation_text, $id);
    print "<br>$local_part\@$domain vacation settings updated\n";
}

# toggle smtp auth feature by ID
sub change_smtp_auth {
    my $id = shift;
    my ($local_part, $domain) =
        mysql_single_row('select local_part, domain from accounts where id = ?', $id);
    access($domain);
    mysql_do('update accounts set smtp_auth = if(smtp_auth, 0, 1) where id = ?', $id);
    print "<br>$local_part\@$domain SMTP feature toggled\n";
}

# toggle antivirus feature by ID
sub change_av {
    my $id = shift;
    my ($local_part, $domain) =
        mysql_single_row('select local_part, domain from accounts where id = ?', $id);
    access($domain);
    mysql_do('update accounts set av_disabled = if(av_disabled, 0, 1) where id = ?', $id);
    print "<br>$local_part\@$domain Anti-Virus feature toggled\n";
}

# change account password in MySQL
sub change_passwd {
    my ($id, $pwd) = @_;
    my ($local_part, $domain) =
        mysql_single_row('select local_part, domain from accounts where id = ?', $id);
    access($domain);
    mysql_do('update accounts set pwd = ? where id = ?', $pwd, $id);
    print "<br>$local_part\@$domain password set\n";
    info("password changed: $local_part\@$domain");
}

# change account quota in MySQL
sub change_quota {
    my ($id, $quota) = @_;
    if ($quota !~ /^\d+$/) {
        print "<strong>Bad quota value</strong> \"$quota\"\n";
        return;
    }
    if (!$superuser && $quota > 10000) { # 10GiB
        print $html_over_space_quota;
        return;
    }
    if (!$superuser && !($quota > 0)) {
        return;
    }
    my ($local_part, $domain, $current_quota) =
        mysql_single_row('select local_part, domain, quota from accounts where id = ?', $id);
    access($domain);
    my $quota_diff = $quota - $current_quota;
    if (!$superuser && $admin_quota + $quota_diff > $admin_max_quota) {
        print $html_over_space_quota;
        return;
    }
    $admin_quota += $quota_diff;
    mysql_do('update accounts set quota = ?, overquota = if(quota < ?, 0, overquota) where id = ?', $quota, $quota, $id);
    mysql_do('update accounts set admin_quota = admin_quota + ? where id in'.
        ' (select acc_id from managed_domains where dom_id = ?)', $quota_diff, $managed_domains->{$domain});
    print "<br>$local_part\@$domain quota set\n";
}

# change administrative account space quota in MySQL
sub change_admin_max_quota {
    return if !$superuser;
    my ($id, $quota) = @_;
    my ($local_part, $domain) =
        mysql_single_row('select local_part, domain from accounts where id = ?', $id);
    mysql_do('update accounts set admin_max_quota = ? where id = ?', $quota, $id);
    print "<br>$local_part\@$domain admin space quota set\n";
}

# change administrative account max account quota in MySQL
sub change_admin_max_accounts {
    return if !$superuser;
    my ($id, $quota) = @_;
    my ($local_part, $domain) =
        mysql_single_row('select local_part, domain from accounts where id = ?', $id);
    mysql_do('update accounts set admin_max_accounts = ? where id = ?', $quota, $id);
    print "<br>$local_part\@$domain admin max accounts quota set\n";
}

# recalculate administrative account quota usage
sub recalc_admin_account_used {
    my $id = shift;
    my ($local_part, $domain) =
        mysql_single_row('select local_part, domain from accounts where id = ?', $id) if $superuser;
    my ($accounts, $quota) =
        mysql_single_row("select count(1), ifnull(sum(quota), 0) from accounts where domain in " .
            "(select domain from domains where id in (select dom_id from managed_domains where acc_id = ?))",
            $id);
    my ($aliases) = mysql_single_row("select count(1) from aliases where domain in " .
            "(select domain from domains where id in (select dom_id from managed_domains where acc_id = ?))",
            $id);
    mysql_do("update accounts set admin_accounts = ?, admin_quota = ? where id = ?", $accounts+$aliases, $quota, $id);
    print "<br>$local_part\@$domain quota usage recalculated\n" if $superuser;
}

sub reload_quota {
    my $id = shift;
    recalc_admin_account_used($id);
    # load user permissions
    ($admin_quota, $admin_accounts) = mysql_single_row("select admin_quota, admin_accounts from accounts where id = ?", $id);
}

# change administrative account list of managed domains in MySQL
sub change_admin_managed_domains {
    return if !$superuser;
    my ($id, $domains) = @_;
    $domains =~ s/\r//g;
    my ($local_part, $domain) =
        mysql_single_row('select local_part, domain from accounts where id = ?', $id);
    mysql_do('delete from managed_domains where acc_id = ?', $id);
    map {
        mysql_do(
            'insert into managed_domains(acc_id, dom_id) select ?, id from domains where domain = ?',
            $id, $_)
    } split(/\n/, $domains);
    print "<br>$local_part\@$domain list of managed domains set\n";
    recalc_admin_account_used($id);
}

# update aliases, use PK IDs from CGI POST data
sub update_aliases {
    my $c = shift;

    my @to_del;
    my %chaliased_to;

    print $html_hr;
    while (my ($k, $v) = each(%$c)) {
        next if $v eq '';
        if ($k eq 'delete') {
            @to_del = ref($v) eq 'ARRAY' ? @$v : $v;
        } elsif ($k =~ /^new_aliased_to_(\d+)$/) {
            $chaliased_to{$1} = $v;
        } elsif ($k ne 'update_aliases' && $k ne 'domain' && $k ne get_cookie_name()) {
           #print "<strong><br>Unknown parameter for alias update: $k</strong>";
        }
    }
   #print "\n<pre>\n";
   #print "to delete:\n";    print Dumper(\@to_del);
   #print "chaliases_to:\n"; print Dumper(\%chaliased_to);

    map { change_aliased_to($_, $chaliased_to{$_}) } keys %chaliased_to;
    map { delete_alias($_) } @to_del;
    print "<br><strong>Aliases Updated</strong>\n";
}

# delete alias from MySQL by ID
sub delete_alias {
    my $id = shift;
    my ($alias, $domain) = mysql_single_row('select alias, domain from aliases where id = ?', $id);
    access($domain);
    mysql_do('delete from aliases where id = ?', $id);
    mysql_do('update accounts set admin_accounts = admin_accounts - 1 where id in'.
        ' (select acc_id from managed_domains where dom_id = ?)', $managed_domains->{$domain});
    print "<br>$alias deleted\n";
    info("alias deleted: $alias");
}

sub append_domain_to_alias {
    my ($aliased_to, $domain) = @_;
    return join ',', map { $_ =~ /\@/ ? $_ : $_ .'@'. $domain } split /\s?,\s?/, $aliased_to;
}

# change alias destination in MySQL
sub change_aliased_to {
    my ($id, $aliased_to) = @_;
    my ($alias, $domain) = mysql_single_row('select alias, domain from aliases where id = ?', $id);
    access($domain);
    $aliased_to = append_domain_to_alias($aliased_to, $domain);
    mysql_do('update aliases set aliased_to = ? where id = ?', $aliased_to, $id);
    print "<br>$alias alias set\n";
}

my $account_i;
# create accounts, use CGI POST data
sub create_accounts {
    my $c = shift;
    my $domain = $c->{domain};
    access($domain);
    my ($smtp_auth, $non_local) = get_domain_settings($domain);

    # can't send welcome mail when delivery is not local, use maildirmake instead
    $send_welcome_mail = 0 if $non_local;

    my @to_create;
    my $total_quota = 0;

    print $html_hr;

    foreach my $a (split /\n/, $c->{new_accounts}) {
        $a =~ tr/\r//d;
        $a =~ s/^\s+//;
        next if $a eq '';
        # account[,20,FirstName,Surname,phone#,other email,other info]
        my @aa = split /,/, $a, 7;
       #print "\n<pre>\n";
       #print "\@aa ($a):\n"; print Dumper(\@aa);
       #print "</pre>\n";
        # ignore domain part - make it easier to paste full emails
        $aa[0] =~ s/\@.*//g;
        if ($aa[0] !~ /^[\w\.-]+$/) {
            print "<br><strong>Unknown account format ignored: \"$a\"</strong>\n";
            next;
        }
        $aa[0] = lc($aa[0]);
        if (defined($aa[1])) { # quota in MB
            if ($aa[1] !~ /^\d+$/) {
                if ($aa[1] ne '') {
                    print "$html_bad_quota_format \"$aa[1]\"\n";
                }
                $aa[1] = $imap_default_quota;
            } else {
                if (!$superuser && !($aa[1] > 0 && $aa[1] <= 10000)) { # 10GiB
                    print "$html_bad_quota_format \"$aa[1]\"\n";
                    $aa[1] = $imap_default_quota;
                }
            }
        } else {
            $aa[1] = $imap_default_quota;
        }
        $total_quota += $aa[1];
        
        # additional DBI bind values
        for (my $i = $#aa + 1; $i < 7; ++$i) {
            push @aa, undef;
        }
        # reset empty string to undef - SQL NULL
        for (my $i = 0; $i <= $#aa; ++$i) {
            if (defined($aa[$i]) && $aa[$i] eq '') {
                undef $aa[$i];
            }
        }
        push @to_create, [@aa];
    }

   #print "\n<pre>\n";
   #print "to create:\n"; print Dumper(\@to_create);
   #print "</pre>\n";

    if (!$superuser) {
	    # the admin user can cheat once by issuing multiple requests in parallel
	    # but as soon as mysql is updated, he'll be overquota
	    reload_quota($user_id);
	    my $overquota = 0;
	    if ($admin_accounts + $#to_create + 1 > $admin_max_accounts) {
	        print $html_over_accounts_quota;
	        $overquota = 1;
	    }
	    if ($admin_quota + $total_quota > $admin_max_quota) {
	        print $html_over_space_quota;
	        $overquota = 1;
	    }
	    return if $overquota;
    }

    print "\n<pre>\n";
    # sort by local_part to output emails in alphabetical order
    $account_i = 1;
    map { create_account($_, $domain, $smtp_auth) } sort { $a->[0] cmp $b->[0] } @to_create;
    print "</pre>\n";
    print "<br><strong>Accounts Created</strong>\n" if $account_i > 1;
    mysql_do('update accounts set admin_accounts = admin_accounts + ?, admin_quota = admin_quota + ? where id in'.
        ' (select acc_id from managed_domains where dom_id = ?)', $account_i-1, $total_quota, $managed_domains->{$domain});
}

my $dev_random_fd = -1;

sub gen_pwd {
    my $pwd = '';

    if (!$pretty_pw) {
        my @pwd_rnd;
        my @pwd_chars = ('A'..'Z', 'a'..'z', '0'..'9');
        if (defined($dev_random)) {
            if ($dev_random_fd == -1) {
                $dev_random_fd = new IO::File;
                open($dev_random_fd, "< $dev_random")
                    || error("Unable to open random device \"$dev_random\": $!");
            }
            my $rnd;
            sysread($dev_random_fd, $rnd, $imap_pwd_len);
            # bias!
            @pwd_rnd = map { $_%($#pwd_chars + 1) } unpack('C' x$imap_pwd_len, $rnd);
        } else {
            for (my $i = 0; $i < $imap_pwd_len; ++$i) {
                push @pwd_rnd, rand($#pwd_chars + 1);
            }
        }
        map { $pwd .= $pwd_chars[$_] } @pwd_rnd;
    } else {
        my @vowels = qw(a e i o u);
        my @consonants = qw(b d f g h k l m n p r s t v z);
        my $alt = int(rand(2));
        for (my $i = 0; $i < $imap_pwd_len; ++$i) {
            if ($alt == 1) {
                $pwd .= $consonants[rand($#consonants + 1)];
                $alt = 0;
            } else {
                $pwd .= $vowels[rand($#vowels + 1)];
                $alt = 1;
            }
        }
    }
    return $pwd;
}

sub account_exists {
    my $account = shift;
    my ($c) = mysql_single_row("select count(1) from accounts where account = ?", $account);
    return $c;
}

# create account given account name and its attributes
sub create_account {
    my ($aa, $domain, $smtp_auth) = @_;
    my ($local_part, $quota) = @$aa;
    my $email = $local_part .'@'. $domain;
    if (account_exists($email)) {
        print "</pre>\n<strong>$email already exists</strong>\n<pre>";
        return;
    }
    my $pwd = gen_pwd();
    mysql_do('insert into accounts (account, local_part, domain, pwd,
        first_name, surname, phone, other_email, info, quota, smtp_auth) values
        (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
        $email, $local_part, $domain, $pwd,
        splice(@$aa, 2), $quota, $smtp_auth);
    if ($send_welcome_mail) {
        if (defined $sendmail) {
            my $h = $welcome_email_headers;
            open(M, "|-", $sendmail, "-t", "-oi")
                || error("Unable to send welcome mail to \"$email\": $!");
            $h =~ s/\$email_to/$email/g;
            print M $h ."\n\n";
        } else {
            open(M, "|-", $bin_mail, "-s", $welcome_subj, $email)
                || error("Unable to send welcome mail to \"$email\": $!");
        }
        print M $welcome_text;
        close(M);
    } elsif (defined $maildirmk) {
        $email =~ /(.*)/; $email = $1; # de-taint for system()
        system($maildirmk, "$imap_spool/$email")
            && error("Unable to create maildir for \"$email\": $!");
        system($maildirmk, '-q', $quota*1024*1024 .'S', "$imap_spool/$email")
            && error("Unable to install maildir quota for \"$email\": $!");
    }
    print "($account_i)\nemail: $email\naccount name: $email\npassword: $pwd\n";
    info("account created: $email");
    ++$account_i;
}

my $alias_i;
# create aliases, use CGI POST data
sub create_aliases {
    my $c = shift;
    my $domain = $c->{domain};
    access($domain);

    my @to_create;

    print $html_hr;

    foreach my $a (split /\n/, $c->{new_aliases}) {
        $a =~ tr/\r//d;
        $a =~ s/^\s+//;
        next if $a eq '';
        # standart alias file format without ':'
        # alias aliased_to,aliased_to2,...
        if ($a !~ /([\w+\.-]+)\s+(.+)/) {
            print "<br><strong>Unknown alias format ignored: \"$a\"</strong>\n";
            next;
        }
        push @to_create, [$1, $2];
    }

   #print "\n<pre>\n";
   #print "to create:\n"; print Dumper(\@to_create);
   #print "</pre>\n";

    if (!$superuser) {
        reload_quota($user_id);
        if ($admin_accounts + $#to_create + 1 > $admin_max_accounts) {
            print $html_over_accounts_quota;
            return;
        }
    }

    $alias_i = 1;
    map { create_alias($_, $domain) } @to_create;
    print "<br><strong>Aliases Created</strong>\n" if $alias_i > 1;
    mysql_do('update accounts set admin_accounts = admin_accounts + ? where id in'.
        ' (select acc_id from managed_domains where dom_id = ?)', $alias_i-1, $managed_domains->{$domain});
}

sub alias_exists {
    my $alias = shift;
    my ($c) = mysql_single_row("select count(1) from aliases where alias = ?", $alias);
    return $c;
}

# create alias given alias name and its attributes
sub create_alias {
    my ($aa, $domain) = @_;
    my ($local_part, $aliased_to) = @$aa;
    my $alias = $local_part .'@'. $domain;
    if (alias_exists($alias)) {
        print "<br><strong>$alias already exists</strong>\n";
        return;
    }
    $aliased_to = append_domain_to_alias($aliased_to, $domain);
    mysql_do('insert into aliases (alias, local_part, domain, aliased_to)
        values
        (?, ?, ?, ?)',
        $alias, $local_part, $domain, $aliased_to);
    print "<br>$alias created\n";
    info("alias created: $alias: $aliased_to");
    ++$alias_i;
}

sub list_overquota {
    opendir(SPOOL, $imap_spool) || error("opendir($imap_spool) failed: $!");
    my @mailboxes = grep { /.+\@.+/ && -d "$imap_spool/$_" } readdir(SPOOL);
    closedir(SPOOL);
    my $no_overquota = 1;
    my $html_overquota;
    foreach my $mbox (@mailboxes) {
        my ($quota, $used, $imap_modified) = imap_info($mbox);
        if ($used > $quota) {
            $no_overquota = 0;
            $quota = int2kib($quota);
            $used  = int2kib($used);
            my $h = $html_overquota_row;
            $mbox =~ /\@(.*)/;
            my $domain = $1;
            $h =~ s/\$domain/$domain/g;
            $h =~ s/\$account/$mbox/g;
            $h =~ s/\$quota_used/$used/g;
            $h =~ s/\$quota/$quota/g;
            $imap_modified = sec2date($imap_modified);
            $h =~ s/\$imap_modified/$imap_modified/g;
            $html_overquota .= $h;
        }
    }
    if ($no_overquota) {
        print "<br><br><strong>No overquota accounts found</strong>\n";
    } else {
        $html_overquota_form =~ s/\$overquota_accounts/$html_overquota/g;
        print $html_overquota_form;
    }
}

my $headers_printed = 0;
# output HTTP headers
sub print_headers {
    return if $headers_printed;
    my $headers = (defined @_) ? "\r\n". join ("\r\n", @_) : ""; # append header(s) from arguments if any
    print "Content-type: text/html; charset=utf-8\r\nExpires: Wed, 27 November 2000 18:00:00 GMT$headers\r\n\r\n";
    $headers_printed = 1;
}

# determine script URL
sub my_base_url {
    my $port = $ENV{'SERVER_PORT'};
    if ((!$https && $port == 80) || ($https && $port == 443)) {
        $port = '';
    }  else {
        $port = ":$port";
    }
    my $script = $ENV{'SCRIPT_NAME'};
   #$script =~ s/^(.*\/)index[^\/]*$/$1/; # may break in unusual configuration
    return 'http' . ($https ? 's' : '') . '://' . $ENV{'SERVER_NAME'} . $port . $script;
}

# get cookie name used for authentification
sub get_cookie_name {
    return "iris_". md5_hex($me);
}

# get hmac key to hash cookie value with 
sub get_hmac_key {
    my $cookie_value = shift;
    # mysql password is used as secret token
    return md5_hex("$cookie_value|$mysql_pwd");
}

# hash username and expiry string to obtain authentication cookie value
sub get_hmac {
    my $cookie_value = shift;
    return hmac_md5_hex($cookie_value, get_hmac_key($cookie_value));
}

# set authentication cookie
sub set_auth_cookie {
    my $user = shift;
    my $expiry = $now + $inactivity_period;
    my $cookie_value = "$user|$expiry|$client_ip";
    $cookie_value .= '|' . get_hmac($cookie_value);
    print 'Set-Cookie: ' . get_cookie_name() . '=' . $cookie_value .
    	'; path=' . $ENV{'SCRIPT_NAME'} . ($https ? '; secure' : '') . ";\r\n";
}

# issue a self-redirect
sub redirect_to_myself {
    my $params = shift;
    $params = '' if !defined $params;
    print "Status: 302 Moved Temporarily\r\n";
    print "Location: $me$params\r\n\r\n";
}

# check user supplied cookie is valid and come from correct IP
sub is_cookie_auth_valid {
    my ($user, $expiry, $ip, $hmac) = split (/\|/, shift);
    return $hmac eq get_hmac("$user|$expiry|$ip") && $ip eq $client_ip;
}

# check the user is authorized to access the domain
sub access {
    return if $superuser;
	my $domain = shift;
	return if exists $managed_domains->{$domain};
    print $html_no_access;
    print $html_end;
    exit(1);
}

sub error {
    my $msg = shift;
    print_headers();
    print "<br>An internal error occured";
    print "<br><strong>$msg</strong>" if $superuser;
    print STDERR "$me: $msg";
    fatal($msg);
    exit(1);
}

my $syslog_connected = 0;

sub connect_syslog {
    return if $syslog_connected;
    setlogsock('unix') if $syslog_unix; # should be 'stream' on solaris
    openlog($0, 'pid', $syslog_facility);
    $syslog_connected = 1;
}

sub _log {
    my ($what, $msg) = @_;
    connect_syslog();
    $msg .= "\n" unless $msg =~ /\n$/;
    if (defined $user) {
        syslog($what, "%s: %s", $user, $msg);
    } else {
        syslog($what, "%s", $msg);
    }
}

sub fatal {
   _log("crit", @_);
}

sub info {
   _log("info", @_);
}

sub main {
    my $post = $ENV{'REQUEST_METHOD'} eq 'POST';

    # parse request
    $cgi = new CGI::Lite;
    my $cgi_data = $cgi->parse_form_data();
    error($cgi->get_error_message()) if $cgi->is_error();
    $cgi->parse_cookies(); # cookies are stuffed into cgi_data

    # user submitted login form
    my $auth_failed = 0;
    if ($post && exists $cgi_data->{login_username} && exists $cgi_data->{login_password}) {
        mysql_connect();
        my $want_login = $cgi_data->{login_username};
        if (verify_login_credentials($want_login, $cgi_data->{login_password})) {
            set_auth_cookie($want_login);
            # user will be redirected to me again, now with cookie set
            redirect_to_myself();
            info("$want_login: login successful");
            exit(0);
        } else {
            info("$want_login: login failed");
            # else we show login form again
            sleep(1);
            $auth_failed = 1;
        }
    }

    # check cookie is present and not expired
    my $cookie_name = get_cookie_name();
    my $cookie_present = 0;
    my $cookie_expires_at;
    if (exists $cgi_data->{$cookie_name} && length($cgi_data->{$cookie_name}) > 0) {
        ($user, $cookie_expires_at) = split(/\|/, $cgi_data->{$cookie_name});
        if ($cookie_expires_at > $now) {
            $cookie_present = 1;
        }
    }
    # no cookie or expired - show login form
    if (!$cookie_present) {
        my $login_username = $auth_failed ? $cgi_data->{login_username} : '';
        $html_login_form =~ s/\$login_username/$login_username/;
        $html_start =~ s/\$user_info//;
        $html_start =~ s/\$logout//;
        print_headers();
        print $html_start;
        print $html_login_form;
        print $html_login_bad_auth if $auth_failed;
        print $html_end;
        exit(0);
    # cookie present
    } else {
        # check it is a valid cookie
        if (!is_cookie_auth_valid($cgi_data->{$cookie_name})) {
            error($cgi_data->{$cookie_name} . " is not a valid cookie");
            exit(1);
        }
        # send next cookie in case current one is at least one minute old, assume $inactivity_period is large enough to trigger this
        if ($cookie_expires_at - $now < $inactivity_period - 60) {
            set_auth_cookie($user);
        }
    }
    # auth is good and $user now holds the user's account name

    # if logout then reset the cookie
    my $logout = exists $cgi_data->{logout};
    if ($logout) {
        print "Set-Cookie: " . get_cookie_name() . "=; path=" . $ENV{'SCRIPT_NAME'} .
            ($https ? "; secure" : "") . ";\r\n";
        $html_start =~ s/\$user_info//;
        $html_start =~ s/\$logout//;
        info("logout");
    } else {
        $html_start =~ s/\$logout/$html_logout_link/;
    }

    print_headers();
    mysql_connect();
 
    # load user permissions
    ($user_id, $superuser, $admin_quota, $admin_accounts, $admin_max_quota, $admin_max_accounts) =
        mysql_single_row(
            "select id, superuser, admin_quota, admin_accounts, admin_max_quota, admin_max_accounts from accounts where account = ?", $user);

    my $info = $user . ($superuser ? '' :
        " ($admin_quota of ${admin_max_quota}MB; $admin_accounts of $admin_max_accounts accounts allocated)");
    $html_user_info =~ s/\$info/$info/;
    $html_start =~ s/\$user_info/$html_user_info/;
    print $html_start;

    if ($debug) {
        print "\n<pre>\n";
        print Dumper($cgi_data);
        print "\n</pre>\n";
    }

    if ($logout) {
        print $html_logged_out;
        print $html_end;
        exit(0);
    }

    # load list of managed domains
    my $q_domains = "select id, domain, disabled, non_local from domains";
    if (!$superuser) {
    	$q_domains .= " where id in (select dom_id from managed_domains where acc_id = ?)";
    }
    $q_domains .= " order by domain";
    my $domains = ($superuser ? mysql_do($q_domains) : mysql_do($q_domains, $user_id))->fetchall_arrayref();
    if (!$superuser && $#$domains == -1) {
        print $html_nothing_to_manage;
        print $html_end;
        exit(0);
    }
    # create a hash: id -> domain; domain -> id
    # [0] is id, [1] is domain name    
    map { $managed_domains->{$_->[1]} = $_->[0] } @$domains;
   #map { $managed_domains->{$_->[0]} = $_->[1]; $managed_domains->{$_->[1]} = $_->[0] } @$domains;
    if ($debug) {
        print "\n<pre>\n";
        print Dumper($managed_domains);
        print "\n</pre>\n";
    }
    my $html_domains;
    # either superuser or more than one managed domain
    if ($superuser || $#$domains > 0) {
        # calculate which domain should be selected in domain list combo-box
        my $focus_domain = exists $cgi_data->{domain} ? $cgi_data->{domain} :
                       ($cgi_data->{text_domain} ? $cgi_data->{text_domain} :
                       ($cgi_data->{select_domain} ? $cgi_data->{select_domain} : ''));

        # prepare domain list combo-box
        my $domain_list = join("\n", ('<option value="choose domain">---choose domain---</option>',
            map {
                # [1] - domain, [2] - disabled, [3] - non local
                my $d = $_->[1];
                my $h = $d;
                if ($_->[2] && $_->[3]) {
                	$h .= ' ---no imap/smtp---';
                } else {
	                $h .= ' ---no imap---' if $_->[2];
	                $h .= ' ---no smtp---' if $_->[3];
                }
                my $selected = ($d eq $focus_domain) ? ' selected' : '';
                "<option value=\"$d\"${selected}>$h</option>"
            } @$domains));
        if ($superuser) {
            $html_domains = $html_domains_superuser;
        } else {
            $html_domains = $html_domains_delegated;
        }
        $html_domains =~ s/\$domain_list/$domain_list/;
    # single delegated domain
    } else {
        $html_domains = $html_domains_single;
        $html_domains =~ s/\$domain/$domains->[0]->[1]/g;
    }
    print $html_domains;

    # for destructive actions allow POST method only
    if (!$post && 
        !exists $cgi_data->{edit_account} &&
        !(exists $cgi_data->{domain_action} && $cgi_data->{domain_action} eq 'Show')) {
        print $html_end;
        exit(1);
    }

    # check edit_account first! see above if !$post
    if (exists $cgi_data->{edit_account}) {
        account_editor($cgi_data->{edit_account});
    } elsif (exists $cgi_data->{domain_action}) {
        my $domain_action = $cgi_data->{domain_action};
        if ($domain_action eq 'Show') {
            my $domain;
            if (exists $cgi_data->{text_domain} && length($cgi_data->{text_domain})) {
                $domain = $cgi_data->{text_domain};
            } elsif (exists $cgi_data->{select_domain}) {
                $domain = $cgi_data->{select_domain};
            } else {
                $domain = $cgi_data->{domain};
            }
            if ($domain eq 'choose domain') {
                 print $html_hr;
                 print "<br><strong>Please select a domain</strong><br>\n";
            } else {
            	access($domain);
            	prepare_show_accounts($domain);
            	prepare_show_aliases($domain);
            	show_domain($domain);
                show_accounts();
                show_create_accounts($domain);
                show_aliases();
                show_create_aliases($domain);
            }
        } elsif ($domain_action eq 'Update') {
            update_domain($cgi_data);
        } elsif ($superuser && ($domain_action eq 'Create' || $domain_action eq 'Remove')) {
            if (!exists $cgi_data->{text_domain} || !length($cgi_data->{text_domain})) {
                 print $html_hr;
                 print "<br><strong>Please enter a domain name</strong><br>\n";
            } else {
                my $domain = $cgi_data->{text_domain};
                if ($domain_action eq 'Create') {
                    create_domain($domain);
                } elsif ($domain_action eq 'Remove') {
                    delete_domain($domain);
                }
            }
        } else {
            error("Unknown domain action: $domain_action");
        }
    } elsif (exists $cgi_data->{update_accounts}) { update_accounts($cgi_data);
    } elsif (exists $cgi_data->{create_accounts}) { create_accounts($cgi_data);
    } elsif (exists $cgi_data->{update_aliases}) {  update_aliases($cgi_data);
    } elsif (exists $cgi_data->{create_aliases}) {  create_aliases($cgi_data);
    } elsif ($superuser && exists $cgi_data->{list_overquota}) { list_overquota();
    } else {
        error("Unknown action");
    }

    print $html_end;
}

MAIN:
{
    main();
}
