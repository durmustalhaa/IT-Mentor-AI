from pathlib import Path
import subprocess

RAW = Path("data/raw")
RAW.mkdir(parents=True, exist_ok=True)

repos = {
    "git-docs": "https://github.com/git/git.git",
    "powershell-docs": "https://github.com/MicrosoftDocs/PowerShell-Docs.git",
    "windows-docs": "https://github.com/MicrosoftDocs/windowsserverdocs.git",
    "linux-docs": "https://github.com/tldr-pages/tldr.git",
    "coreutils-docs": "https://git.savannah.gnu.org/git/coreutils.git",
    "grep-docs": "https://git.savannah.gnu.org/git/grep.git",
    "docker-docs": "https://github.com/docker/cli.git",
    "windows-powershell-docs": "https://github.com/MicrosoftDocs/windows-powershell-docs.git",
    "nftables-docs": "https://github.com/Mic92/nftables.git",
    "cron-docs": "https://github.com/cronie-crond/cronie.git",
    "iptables-docs": "https://github.com/Distrotech/iptables.git",
    "ufw-docs": "https://git.launchpad.net/ufw",
    "ssh-docs": "https://github.com/openssh/openssh-portable.git",
    "apt-docs": "https://github.com/Debian/apt.git",
    "dnf-docs": "https://github.com/rpm-software-management/dnf.git",
}

for name, url in repos.items():
    target = RAW / name

    if target.exists():
        print(f"{name} zaten mevcut.")
        continue

    print(f"{name} indiriliyor...")
    subprocess.run(
        ["git", "clone", "--depth", "1", url, str(target)],
        check=True,
    )

# systemd'nin tam deposu Windows'ta klonlanamıyor: test klasöründeki bazı
# dosya adları (ör. "id:000000,sig:06,...") Windows'ta yasak ":" karakteri
# içeriyor, düz "git clone" checkout aşamasında hata veriyor. Sadece
# ihtiyacımız olan man/ klasörünü sparse-checkout ile çekiyoruz.
systemd_target = RAW / "systemd-docs"

if systemd_target.exists():
    print("systemd-docs zaten mevcut.")
else:
    print("systemd-docs indiriliyor (sadece man/ - sparse checkout)...")
    systemd_target.mkdir(parents=True, exist_ok=True)
    run = lambda *args: subprocess.run(args, cwd=systemd_target, check=True)
    run("git", "init", "-q")
    run("git", "remote", "add", "origin", "https://github.com/systemd/systemd.git")
    run("git", "config", "core.sparseCheckout", "true")
    run("git", "sparse-checkout", "init", "--cone")
    run("git", "sparse-checkout", "set", "man")
    run("git", "fetch", "--depth", "1", "origin", "main")
    run("git", "checkout", "origin/main", "--", "man")

print("Tüm kaynaklar indirildi.")

print(
    "\nNot: 'windows-shortcuts' kaynağı bu script tarafından indirilmez - "
    "support.microsoft.com'daki resmi klavye kısayolları sayfasından elle "
    "çekilip data/raw/windows-shortcuts/shortcuts.md olarak kaydedilmiştir. "
    "Bu dosya sıfırdan kurulumda elle yeniden oluşturulmalıdır."
)