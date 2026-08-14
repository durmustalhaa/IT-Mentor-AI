from pathlib import Path

RAW_DIR = Path("data/raw")

SOURCES = {
    "git-docs": {
        "allowed_dirs": [
            "Documentation"
        ],
        "extension": ".adoc",
        "format": "git-adoc",
        # Alt klasörler (RelNotes, config, howto, technical...) komut
        # referansı değil; sürüm notları ve config-key parçaları içerir.
        "recursive": False
    },

    "powershell-docs": {
        # "reference" klasörünün altındaki docs-conceptual/includes/module gibi
        # klasörler cmdlet referansı değil, dil/stil rehberi niteliğinde
        # kavramsal makaleler içeriyor; sadece gerçek cmdlet referansı olan
        # sürüm klasörleri alınıyor.
        "allowed_dirs": [
            "reference/5.1",
            "reference/7.4",
            "reference/7.5",
            "reference/7.6",
            "reference/7.7"
        ],
        "extension": ".md",
        "format": "powershell-md"
    },

    "windows-docs": {
        "allowed_dirs": [
            "WindowsServerDocs",
            "EssentialsDocs"
        ],
        "extension": ".md",
        "format": "powershell-md"
    },

    "linux-docs": {
        # tldr'ın common/linux klasörleri masaüstü uygulamaları, oyunlar,
        # dile özel dev araçları gibi IT operasyonlarıyla alakasız binlerce
        # sayfa içeriyor (ör. yacas, kahlan, picom). Sadece gerçek sistem
        # yönetimi komutlarıyla sınırlandırılıyor.
        "allowed_dirs": [
            "pages/common",
            "pages/linux"
        ],
        "extension": ".md",
        "format": "tldr-md",
        "allowed_names": {
            # Dosya/metin işleme
            "ls", "cat", "less", "more", "head", "tail", "grep", "egrep",
            "fgrep", "sed", "awk", "cut", "sort", "uniq", "wc", "tr", "find",
            "xargs", "tee", "diff", "patch", "cmp", "split", "tar", "gzip",
            "unzip", "cp", "mv", "rm", "mkdir", "ln", "touch", "stat",
            "basename", "dirname", "realpath", "readlink", "tree", "rsync",
            "dd", "shred", "base64", "md5sum", "sha256sum", "jq", "nl",
            "paste", "join", "comm", "tac", "rev", "column", "fold", "expand",
            "unexpand",

            # Süreç / sistem yönetimi
            "ps", "top", "htop", "kill", "killall", "pkill", "nice", "nohup",
            "uptime", "free", "vmstat", "iostat", "lsof", "strace", "ltrace",
            "systemctl", "journalctl", "service", "dmesg", "uname",
            "hostnamectl", "timedatectl", "crontab", "at", "watch", "env",
            "alias", "history", "whoami", "who", "w", "last", "id", "groups",
            "sysctl", "shutdown", "reboot", "systemd-analyze", "wall",

            # Ağ
            "ip", "ifconfig", "ping", "traceroute", "mtr", "dig", "nslookup",
            "netstat", "ss", "curl", "wget", "ssh", "ssh-copy-id",
            "ssh-keygen", "scp", "sftp", "nmap", "telnet", "nc", "iptables",
            "ufw", "route", "arp", "hostname", "wol", "ethtool", "nmcli",

            # İzinler / kullanıcılar
            "chmod", "chown", "chgrp", "umask", "sudo", "su", "useradd",
            "userdel", "usermod", "groupadd", "groupdel", "passwd", "chage",
            "visudo", "setfacl", "getfacl", "adduser", "deluser",

            # Disk / dosya sistemi
            "df", "du", "mount", "umount", "fdisk", "parted", "mkfs", "fsck",
            "lsblk", "blkid", "findmnt", "swapon", "lvcreate", "vgcreate",
            "pvcreate",

            # Paket yöneticileri
            "apt", "apt-get", "apt-cache", "dpkg", "yum", "dnf", "rpm",
            "pacman", "snap", "flatpak", "brew", "apk",

            # Container / sanallaştırma
            "docker", "docker-compose", "podman", "kubectl", "vagrant",

            # Editör / kabuk
            "vim", "nano", "bash", "sh", "source", "echo", "printf", "read",
            "test", "expr", "clear", "exit", "type",

            # Güvenlik / diğer
            "openssl", "gpg", "whois", "date", "man", "which", "whereis",
            "tmux", "screen"
        }
    },

    "windows-shortcuts": {
        # Git reposu değil - support.microsoft.com'daki resmi "Keyboard
        # shortcuts in Windows" sayfasından elle çekilip data/raw/'a
        # kaydedilmiş bir dosya. download_sources.py bunu klonlamaz.
        "allowed_dirs": [
            "."
        ],
        "extension": ".md",
        "format": "shortcut-list",
        "recursive": False
    },

    "coreutils-docs": {
        # GNU coreutils'in texinfo kılavuzu; ls/cp/mv/chmod/df gibi komutların
        # TÜM seçeneklerini eksiksiz listeler (tldr sadece örnek kullanım
        # gösteriyordu, tam referans değildi).
        "allowed_dirs": [
            "doc"
        ],
        "extension": ".texi",
        "format": "coreutils-texi",
        "recursive": False
    },

    "grep-docs": {
        # GNU grep'in kendi texinfo kılavuzu - coreutils'ten farklı olarak
        # standart @table @option / @item / @itemx makrolarını kullanıyor
        # (özel @optItem makrosu yok) ve TEK dosya TEK komutu belgeliyor.
        "allowed_dirs": [
            "doc"
        ],
        "extension": ".texi",
        "format": "gnu-manual-texi",
        "recursive": False
    },

    "systemd-docs": {
        # systemd'nin kendi DocBook XML kılavuzu (man/*.xml) - 484 dosyanın
        # çoğu iç API/D-Bus referansı, IT operasyonuyla ilgisiz. Sadece
        # gerçekten günlük kullanılan CLI araçları (systemctl, journalctl...)
        # ve en sık düzenlenen unit dosyası direktif setleri (systemd.service,
        # systemd.timer...) alınıyor - linux-docs'taki allowed_names ile aynı
        # kürasyon prensibi.
        "allowed_dirs": [
            "man"
        ],
        "extension": ".xml",
        "format": "systemd-docbook-xml",
        "recursive": False,
        "allowed_names": {
            "systemctl", "journalctl", "systemd-analyze", "systemd-run",
            "loginctl", "timedatectl", "hostnamectl",
            "systemd.unit", "systemd.service", "systemd.timer",
            "systemd.socket", "systemd.exec", "systemd.mount",
            "systemd.path", "systemd.kill", "systemd.resource-control",
            # Round-C audit'te "networkctl list ne yapar?" gibi sorular bu
            # araçların hiç kürasyona alınmadığını ortaya çıkardı - dosyalar
            # zaten data/raw/systemd-docs/man/ altında (aynı repo, aynı
            # sparse checkout), sadece bu listeye hiç eklenmemişlerdi.
            "networkctl", "busctl", "machinectl", "portablectl",
            "resolvectl"
        }
    },

    "windows-powershell-docs": {
        # Windows Server rol/özellik modüllerinin PowerShell cmdlet
        # referansı (ActiveDirectory, ScheduledTasks, NetSecurity/Windows
        # Firewall, DNS/DHCP, networking) - powershell-docs'tan AYRI bir
        # repo, ama AYNI formatı (### -ParamName alt başlıkları)
        # kullanıyor, bu yüzden mevcut "powershell-md" parser'ı hiç
        # değiştirmeden yeniden kullanılabiliyor. ~140 modülden IT
        # operasyonlarıyla doğrudan ilgili olanlar seçildi.
        "allowed_dirs": [
            "docset/winserver2025-ps/ActiveDirectory",
            "docset/winserver2025-ps/ScheduledTasks",
            "docset/winserver2025-ps/NetSecurity",
            "docset/winserver2025-ps/DhcpServer",
            "docset/winserver2025-ps/DnsServer",
            "docset/winserver2025-ps/DnsClient",
            "docset/winserver2025-ps/NetTCPIP",
            "docset/winserver2025-ps/NetAdapter",
            "docset/winserver2025-ps/NetConnection",
            "docset/winserver2025-ps/GroupPolicy"
        ],
        "extension": ".md",
        "format": "powershell-md"
    },

    "cron-docs": {
        # cronie'nin (Debian/RHEL'in ikisinin de türediği Vixie/ISC cron
        # soyu) kendi klasik troff man sayfaları - crontab(1)/crontab(5)/
        # cron(8)/crond(8)/anacron(8)/anacrontab(5)/cronnext(1). Aynı
        # klasörde üç farklı bölüm-numarası uzantısı bir arada.
        "allowed_dirs": [
            "man"
        ],
        "extension": [".1", ".5", ".8"],
        "format": "troff-man",
        "recursive": False
    },

    "iptables-docs": {
        # iptables'ın kendi troff man sayfaları. Ana komutlar (iptables,
        # ip6tables) autoconf şablonu olduğu için ".8.in" ile bitiyor;
        # save/restore/apply yardımcıları düz ".8". iptables-extensions.8.in
        # bilerek DIŞARIDA - o sadece 28 satırlık bir iskelet; gerçek
        # match/target modülü içeriği extensions/*.man'de ayrıca taranıyor
        # (aşağıdaki "iptables-extensions-docs" girdisi).
        #
        # allowed_names KASITLI OLARAK yok: pathlib .stem "iptables.8.in"
        # için sadece SON uzantıyı (".in") keser, "iptables.8" verir - bir
        # allowed_names={"iptables"} kontrolü bu yüzden dosyayı sessizce
        # elerdi (gerçekten oldu, fark edildi). "iptables" klasörü zaten
        # allowed_dirs ile dar olduğu için filtreye gerek yok.
        "allowed_dirs": [
            "iptables"
        ],
        "extension": [".8.in", ".8"],
        "format": "troff-man",
        "recursive": False
    },

    "iptables-extensions-docs": {
        # `--dport`/`--sport`/`--tcp-flags`/`--syn`/`--state` gibi en sık
        # sorulan iptables bayrakları ana iptables.8.in'de HİÇ yok - onlar
        # match/target UZANTILARININ (tcp, udp, state, limit...) kendi
        # ayrı belgeleri, extensions/*.man altında. Bu 94 dosya daha önce
        # "build zamanında birleştiriliyor, ayrı parser gerekir" diye
        # bilerek dışarıda bırakılmıştı - ama her parça dosya zaten kendi
        # başına geçerli bir `.TP` blok dizisi (sadece `.SH` başlıkları
        # yok), @TARGET@/@MATCH@ birleştirme mekanizmasını hiç çözmeye
        # gerek kalmadan doğrudan taranabiliyor. "repo" ile aynı
        # iptables-docs klonu, farklı bir alt klasör ve format ile ikinci
        # kez taranıyor.
        "repo": "iptables-docs",
        "allowed_dirs": [
            "extensions"
        ],
        "extension": ".man",
        "format": "iptables-extension-man",
        "recursive": False
    },

    "ufw-docs": {
        # ufw'nin kendi troff man sayfası (doc/ufw.8).
        "allowed_dirs": [
            "doc"
        ],
        "extension": ".8",
        "format": "troff-man",
        "recursive": False
    },

    "ssh-docs": {
        # OpenSSH'ın kendi kılavuz sayfaları - BSD mdoc formatında
        # (.Sh/.Nm/.Bl/.It Fl/.Ar/.Xr...), troff-man'den (crontab/iptables/
        # ufw) TAMAMEN farklı bir makro sözlüğü, bu yüzden ayrı bir parser
        # ("mdoc-man") gerekti. Repo kökünde tek klasörde tüm man sayfaları.
        "allowed_dirs": [
            "."
        ],
        "extension": [".1", ".5", ".8"],
        "format": "mdoc-man",
        "recursive": False
    },

    "dnf-docs": {
        # dnf'in kendi reStructuredText kılavuzu - sadece CLI/config
        # referansı olan iki dosya alınıyor (repo'nun geri kalanı Python
        # API dokümantasyonu, IT-ops kapsamı dışında).
        "allowed_dirs": [
            "doc"
        ],
        "extension": ".rst",
        "format": "dnf-rst",
        "recursive": False,
        "allowed_names": {"command_ref", "conf_ref"}
    },

    "apt-docs": {
        # apt'nin kendi DocBook XML kılavuzları (apt-get, apt-cache,
        # apt-mark, apt.conf, sources.list gibi hem CLI araçları hem
        # config dosyası referansları) - systemd/nftables ile AYNI format,
        # aynı parser yeniden kullanılıyor. Tek fark: apt'nin entity
        # adları nokta/tire içerebiliyor (preprocess_docbook_xml'de
        # genelleştirildi).
        "allowed_dirs": [
            "doc"
        ],
        "extension": ".xml",
        "format": "systemd-docbook-xml",
        "recursive": False
    },

    "nftables-docs": {
        # nftables'ın kendi DocBook XML kılavuzu (doc/nft.xml) - systemd
        # ile AYNI formatı kullanıyor, aynı parser (systemd-docbook-xml)
        # yeniden kullanılıyor. Tek fark: kısa/uzun flag formunu AYRI
        # <term> yerine tek <option> içinde "/" ile birleştiriyor
        # (ör. "-h/--help") - parser bunu genel olarak destekliyor.
        "allowed_dirs": [
            "doc"
        ],
        "extension": ".xml",
        "format": "systemd-docbook-xml",
        "recursive": False
    },

    "docker-docs": {
        # docker/cli'nin kendi ürettiği CLI referansı - her komut/alt komut
        # kendi .md dosyasında, düzenli bir Options tablosuyla. Birçok komut
        # aynı anda hem eski düz isimle (run.md) hem yeni namespaced isimle
        # (container_run.md) iki ayrı dosyada duplike ediliyor; namespaced
        # olan her zaman daha zengin (Description + Examples de var) - bu
        # yüzden parser, "### Aliases" bölümü olan düz (alt çizgisiz)
        # dosyaları atlayıp sadece namespaced/tekil olanı işliyor.
        "allowed_dirs": [
            "docs/reference/commandline"
        ],
        "extension": ".md",
        "format": "docker-cli-md",
        "recursive": False
    }
}