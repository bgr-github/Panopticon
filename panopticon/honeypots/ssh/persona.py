"""A deliberately fixed, internally consistent Ubuntu host persona."""

HOSTNAME = "web-01"
KERNEL = "6.8.0-31-generic"
KERNEL_BUILD = "#31-Ubuntu SMP PREEMPT_DYNAMIC Sat Apr 20 00:40:06 UTC 2024"
SSH_VERSION = "OpenSSH_9.6p1 Ubuntu-3ubuntu13"
OS_RELEASE = '''PRETTY_NAME="Ubuntu 24.04 LTS"
NAME="Ubuntu"
VERSION_ID="24.04"
VERSION="24.04 LTS (Noble Numbat)"
VERSION_CODENAME=noble
ID=ubuntu
ID_LIKE=debian
HOME_URL="https://www.ubuntu.com/"
SUPPORT_URL="https://help.ubuntu.com/"
BUG_REPORT_URL="https://bugs.launchpad.net/ubuntu/"
PRIVACY_POLICY_URL="https://www.ubuntu.com/legal/terms-and-policies/privacy-policy"
UBUNTU_CODENAME=noble
LOGO=ubuntu-logo
'''
MOTD = f"""Welcome to Ubuntu 24.04 LTS (GNU/Linux {KERNEL} x86_64)

 * Documentation:  https://help.ubuntu.com
 * Management:     https://landscape.canonical.com
 * Support:        https://ubuntu.com/pro

"""
