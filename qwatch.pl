#!/usr/bin/perl -w

my $log_file = '{{exim_log_dir}}/mainlog';
my $imap_spool = '{{imap_dir}}';
my $log_poll_interval = 30;
my $mbox_recheck_interval = 300;
my $over_quota_str = 'defer (-22): mailbox is full (MTA-imposed quota exceeded while writing to';
# comment out to disable scan for big messages, see README
my $too_big_str = ': message too big: ';
# forget about "too big messages" every N seconds and start from scratch
my $too_big_reset = 10000;
my $mysql_host = 'localhost;mysql_socket=/tmp/mysql.sock';
my $mysql_db   = 'mail';
my $mysql_user = 'iris';
my $mysql_pwd  = '{{mysql_iris_password}}';

my $debug = 0;

use strict;
use DBI;
use Sys::Syslog qw(:DEFAULT setlogsock);
eval 'use Data::Dumper;' if $debug;

sub _log {
    syslog('info', '%s', $_[0]);
}

sub is_overquota {
    my $email = shift;
    my $mdirsz = $imap_spool .'/'. $email .'/maildirsize';
    open(S, "< $mdirsz") || return 0;
    my $first_line = <S>;
    my ($quota) = $first_line =~ /(\d+)S/i;
    (close(S), return 0) unless defined $quota;
    my $quota_used = 0;
    while (<S>) {
        $quota_used += (split)[0];
    }
    close(S);
   #return 1 if $quota <= $quota_used;
    # IMAP quota might differs from what is set via web panel
    return 1 if get_quota_from_db($email) <= $quota_used;
    return 0;
}

sub open_log {
    print "open_log\n" if $debug;
    open(L, "< $log_file") || (_log("$log_file: $!"), die "$log_file: $!");
    my $size = (stat(L))[7];
    seek(L, $size, 0); # might miss something when re-opening, but prevents false asmtp_off at start-up
}

my $mysql;

sub mysql_connect {
    return if defined $mysql;
    $mysql = DBI->connect("dbi:mysql:dbname=$mysql_db;host=$mysql_host", $mysql_user, $mysql_pwd);
}

sub mysql_disconnect {
    return unless defined $mysql;
   #$mysql->commit();
    $mysql->disconnect();
    undef $mysql;
}

sub mysql_do {
    my ($sql, @bind_values) = @_;
    my $stm = $mysql->prepare($sql) || (print STDERR "MySQL prepare($sql) failed: ". $mysql->errstr, return undef);
    $stm->execute(@bind_values)     || (print STDERR "MySQL execute($sql) failed: ". $mysql->errstr, return undef);
    return $stm;
}

sub get_quota_from_db {
    my $email = shift;
    mysql_connect();
    my $r = mysql_do('select quota from accounts where account = ?', $email);
    my ($quota) = $r->fetchrow_array();
    return $quota*1024*1024;
}

sub set_overquota {
    my ($email, $q) = @_;
    _log("set_overquota $email $q");
    mysql_connect();
    return mysql_do('update accounts set overquota = ? where account = ?', $q, $email);
}

sub set_asmtp_off {
    my ($email) = @_;
    _log("set_asmtp_off $email");
    mysql_connect();
    return mysql_do('update accounts set smtp_auth = 0 where account = ?', $email);
}

    setlogsock('unix');
    openlog($0, 'pid', 'mail');

    _log("qwatch started");
    open_log();

    my %to_check;
    my %asmtp_off;
    my %ignore_big;
    mysql_connect();
    my $sel = mysql_do("select account from accounts where overquota = 1") || die;
    while (my $row = $sel->fetchrow_hashref()) {
        $to_check{$row->{account}} = 2;
    }
    print "read from db:\n". Dumper(\%to_check) if $debug;
    mysql_disconnect();

    my $last_check_time = 0;
    my $last_big_reset = time();
    while (1) {
        my $no_logs = 1;
        print "trying to read\n" if $debug;
        while (my $l = <L>) {
            $no_logs = 0;
            if (index($l, $over_quota_str) != -1) {
                my $email = (split / /, $l, 6)[4];
                $to_check{$email} = 1 unless defined $to_check{$email};
                _log("mta reported overquota $email");
            }
            if (defined $too_big_str && index($l, $too_big_str) != -1) {
                if (my ($email) = $l =~ /rejected (?:from |MAIL FROM:)<([\w_.-]+\@[\w_.-]+)>/) {
                    if (exists $asmtp_off{$email}) {
                        ++$asmtp_off{$email}
                    } else {
                        $asmtp_off{$email} = 1;
                    }
                    _log("mta reported smtp message too big $email");
                }
            }
        }
        if ($no_logs) {
            print "no logs\n" if $debug;
            my $ino = (stat(L))[1];
            my $pos = tell(L);
            my ($new_ino, $new_size) = (stat($log_file))[1,7];
            if ($ino != $new_ino || $new_size < $pos) {
                _log("reopening log $log_file");
                close(L);
                open_log();
            }
        } else { print "read something\n" if $debug; }

        foreach my $email (keys %asmtp_off) {
            if (!exists $ignore_big{$email} && $asmtp_off{$email} > 3) {
                _log("setting asmtp off $email");
                set_asmtp_off($email);
                $ignore_big{$email} = 1;
                delete $asmtp_off{$email};
            }
        }

        my $now = time();
        if ($now > $last_check_time + $mbox_recheck_interval) {
            print "check pass\n" if $debug;
            foreach my $email (keys %to_check) {
                print "checking $email\n" if $debug;
                if (is_overquota($email)) {
                    set_overquota($email, 1) || last if $to_check{$email} == 1;
                    $to_check{$email} = 2;
                } else {
                    set_overquota($email, 0) || last if $to_check{$email} == 2;
                    delete $to_check{$email};
                }
            }
            mysql_disconnect();
            $last_check_time = $now;
        }
        if ($now > $last_big_reset + $too_big_reset) {
            undef %asmtp_off;
            undef %ignore_big;
            $last_big_reset = $now;
        }
        print "to_check:\n". Dumper(\%to_check) if $debug;
        print "asmtp_off:\n". Dumper(\%asmtp_off) if $debug;
        print "ignore_big:\n". Dumper(\%ignore_big) if $debug;
        sleep($log_poll_interval);
    }
