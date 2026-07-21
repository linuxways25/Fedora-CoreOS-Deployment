# Fedora-CoreOS-Deployment
The goal is to create an intelligent deployment agent that runs on your Arch Linux/CachyOS host and deploy Fedora CoreOS Qcow2 VM into KVM (QEMU)

FCOS-Agent-v5 — Complete Task Sequence

Start the Python agent.

Parse command-line arguments and configuration.

Detect the host operating system.

Detect CPU architecture.

Detect available CPU cores.

Detect available RAM.

Detect available disk space.

Check hardware virtualization support.

Verify /dev/kvm.

Verify QEMU installation.

Verify qemu-img.

Verify libvirt installation.

Verify virsh.

Verify SSH client availability.

Connect to qemu:///system.

Check libvirt service status.

Check libvirt permissions.

List available libvirt networks.

Detect the usable network.

Start the network if inactive.

Verify DHCP availability.

Detect the network bridge.

Search for existing SSH keys.

Select the best available SSH key.

Validate the SSH public key.

Validate the SSH private key.

Validate SSH key permissions.

Load the SSH public key.

Check whether the Fedora CoreOS
QCOW2 image exists.

Download the image if missing.

Validate image format and readability.

Verify image integrity/checksum.

Check whether the target VM already exists.

Determine the existing VM state.

Decide whether to reuse, start, or recreate the VM.

Create the deployment workspace.

Generate the Ignition configuration.

Configure the core user.

Inject the SSH public key.

Configure hostname and system settings.

Add required files and services.

Save the Ignition configuration.

Validate Ignition JSON syntax.

Validate Ignition configuration structure.

Validate SSH and user configuration.

Prepare or clone the VM disk.

Resize the disk if required.

Validate disk accessibility and permissions.

Configure VM CPU.

Configure VM memory.

Configure VM storage.

Configure VM networking.

Attach the Fedora CoreOS disk.

Attach the Ignition configuration.

Configure VM boot settings.

Define the VM in libvirt.

Start the Fedora CoreOS VM.

Verify the VM is running.

Monitor the initial boot process.

Wait for Fedora CoreOS initialization.

Detect the VM MAC address.

Query libvirt DHCP leases.

Discover the VM IP address automatically.

Validate the discovered IP address.

Retry IP discovery if necessary.

Check whether TCP port 22 is open.

Wait for the SSH service.

Retry SSH connection if necessary.

Authenticate using the detected SSH key.

Verify successful SSH login.

Verify the Fedora CoreOS operating system.

Verify hostname and kernel.

Verify system uptime.

Check failed systemd services.

Check CPU utilization.

Check memory availability.

Check disk space.

Check network connectivity.

Verify Ignition completion.

Perform a complete system health check.

Detect deployment failures.

Collect diagnostic information.

Identify the root cause of failures.

Apply safe automatic recovery actions.

Retry failed operations.

Re-verify the recovered system.

Generate the deployment report.

Save execution logs.

Save diagnostic information.

Display VM name, IP address, user, and status.

Display the final SSH command.

Report deployment success or failure.

Exit with the appropriate status code.