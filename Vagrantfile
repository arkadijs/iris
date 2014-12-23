# -*- mode: ruby; -*-

# This is a slightly modified copy of
# https://github.com/arkadijs/vagrant-freebsd/blob/master/Vagrantfile

Vagrant.configure("2") do |config|
  config.vm.guest = :freebsd
  config.vm.box = "freebsd-10.1-i386"
  config.vm.box_url = "http://iris.hosting.lv/freebsd-10.1-i386.box"

  # The box has 2 vtnet adapters configured:
  # vtnet0 => nat
  # vtnet1 => host-only
  # Adapters are renamed by FreeBSD rc.conf to em0,1

  # Create a forwarded port mapping which allows access to a specific port
  # within the machine from a port on the host machine. In the example below,
  # accessing "localhost:8080" will access port 80 on the guest machine.
  config.vm.network :forwarded_port, guest:  80, host: 9080, auto_correct: true
  config.vm.network :forwarded_port, guest: 443, host: 7443, auto_correct: true
  config.vm.network :forwarded_port, guest: 943, host: 7943, auto_correct: true

  # Create a private network, which allows host-only access to the machine
  # using a specific IP.
  config.vm.network :private_network, ip: "192.168.33.10", adapter: 2

  # Create a public network, which generally matched to bridged network.
  # Bridged networks make the machine appear as another physical device on
  # your network.
  # config.vm.network :public_network

  # If true, then any SSH connections made will enable agent forwarding.
  # Default value: false
  # config.ssh.forward_agent = true

  # Share an additional folder to the guest VM. The first argument is
  # the path on the host to the actual folder. The second argument is
  # the path on the guest to mount the folder. And the optional third
  # argument is a set of non-required options.
  # config.vm.synced_folder "../data", "/vagrant_data"
  config.vm.synced_folder ".", "/vagrant", nfs: true

  config.vm.provider :virtualbox do |vb|
    vb.gui = true
    vb.customize ["modifyvm", :id, "--memory", "512"]
   #vb.customize ["modifyvm", :id, "--cpus", "2"]
    vb.customize ["modifyvm", :id, "--ioapic", "on"]
    vb.customize ["modifyvm", :id, "--hwvirtex", "on"]
    vb.customize ["modifyvm", :id, "--usb", "off"]
    vb.customize ["modifyvm", :id, "--usbehci", "off"]
    vb.customize ["modifyvm", :id, "--audio", "none"]
    vb.customize ["modifyvm", :id, "--nictype1", "virtio"]
    vb.customize ["modifyvm", :id, "--nictype2", "virtio"]
  end

  config.vm.provision :shell, :path => "provision/bootstrap.sh"
  config.vm.provision "ansible" do |ansible|
    ansible.playbook = "provision/playbook.yml"
    ansible.host_key_checking = false
   #ansible.verbose = 'vvvv'
  end

end
