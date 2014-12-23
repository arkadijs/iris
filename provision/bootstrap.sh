#!/bin/sh

# comment out to disable
do_portsnap=1
#install_from_ports=1

set -xe
uname -a

# if grep -q ifconfig_em1 /etc/rc.conf; then echo em1 config already exists in rc.conf; else
#     /sbin/ifconfig em1 inet 192.168.33.10 netmask 255.255.255.0
#     echo 'ifconfig_em1="inet 192.168.33.10 netmask 255.255.255.0"' >>/etc/rc.conf
#     em1_banner="You may now uncomment 'config.vm.synced_folder \".\", \"/vagrant\", nfs: true' in Vagrantfile"
# fi

if [ ! -f /tmp/freebsd-update ]; then
	sed 's/\[ ! -t 0 \]/false/' /usr/sbin/freebsd-update >/tmp/freebsd-update
	chmod +x /tmp/freebsd-update
	PAGER=/bin/cat /tmp/freebsd-update fetch
	PAGER=/bin/cat sh -c '/tmp/freebsd-update install; exit 0'
fi

if [ -n "$do_portsnap" -a ! -d /usr/ports ]; then
	if grep -q "REFUSE accessibility" /etc/portsnap.conf; then echo no portsnap.conf updates necessary; else
		cat >>/etc/portsnap.conf <<EOF
REFUSE accessibility arabic astro benchmarks biology cad
REFUSE chinese deskutils distfiles finance french
REFUSE games german hebrew hungarian japanese korean
REFUSE palm polish portuguese russian ukrainian vietnamese
#REFUSE x11 x11-clocks x11-drivers x11-fm x11-fonts x11-servers x11-themes x11-toolkits x11-wm
EOF
	fi
	/usr/sbin/portsnap --interactive fetch
	if [ -f /usr/ports/.portsnap.INDEX ]; then /usr/sbin/portsnap update; else /usr/sbin/portsnap extract >/dev/null; fi
fi

if grep -q "NO_PROFILE" /etc/make.conf; then echo no make.conf updates necessary; else
	cat >/etc/make.conf <<EOF
NO_PROFILE= YES
WITHOUT_BLUETOOTH= YES
WITHOUT_CUPS= YES
WITHOUT_FLOPPY= YES
WITHOUT_GAMES= YES
WITHOUT_GUI= YES
WITHOUT_USB= YES
WITHOUT_WIRELESS= YES
WITHOUT_WPA_SUPPLICANT_EAPOL= YES
WITHOUT_X11= YES
EOF
fi

pkg bootstrap
pkg update

# echo 'rpcbind_enable="YES"' >> /etc/rc.conf
# echo 'nfs_client_enable="YES"' >> /etc/rc.conf
# echo 'nfs_server_enable="YES"' >> /etc/rc.conf
# echo 'mountd_flags="-r"' >> /etc/rc.conf

if [ -z "$install_from_ports" ]; then
	pkg install -y python27 nano
else
	if [ ! -f /usr/local/bin/python2.7 ]; then
		cd /usr/ports/lang/python27
		make -DBATCH install clean
	fi

	if [ ! -f /usr/local/bin/nano ]; then
		cd /usr/ports/editors/nano
		make -DBATCH install clean
	fi
fi

echo done
echo "$em1_banner"
