#!/bin/bash
# One-line installer for ppcosxkvm:
#
#   curl -fsSL https://raw.githubusercontent.com/linuxkid473/ppcosxkvm/main/install.sh | bash
#
# Clones (or updates) the project into ~/.ppcosx, builds QEMU, and puts the
# `ppcosx` command on your PATH.  Re-running it updates an existing install.
#
#   PPCOSX_HOME=/some/dir   install somewhere else (default ~/.ppcosx)
#   PPCOSX_BRANCH=name      install another branch (default main)
#   PPCOSX_REPO=url         install from a fork
#
# Everything is inside main(), which runs on the last line: under
# `curl | bash`, bash has then read the whole script before any command
# (brew, git) gets a chance to read from stdin.

main() {
    set -u
    local repo_url="${PPCOSX_REPO:-https://github.com/linuxkid473/ppcosxkvm.git}"
    local dir="${PPCOSX_HOME:-$HOME/.ppcosx}"
    local branch="${PPCOSX_BRANCH:-main}"
    local B= R= G= Y= N=
    if [ -t 2 ]; then
        B=$'\033[1m'; R=$'\033[31m'; G=$'\033[32m'; Y=$'\033[33m'; N=$'\033[0m'
    fi
    say()  { printf '%s==>%s %s\n' "$B" "$N" "$*" >&2; }
    fail() { printf '%serror:%s %s\n' "$R" "$N" "$*" >&2; exit 1; }

    printf '%sppcosxkvm installer%s - PowerPC Mac OS X on Apple Silicon\n\n' "$B" "$N" >&2

    [ "$(uname -s)" = Darwin ] || fail "ppcosxkvm runs on macOS only."
    if [ "$(uname -m)" != arm64 ]; then
        printf '%s!%s This is not an Apple Silicon Mac; continuing, but it is untested.\n' "$Y" "$N" >&2
    fi

    if ! xcode-select -p >/dev/null 2>&1; then
        xcode-select --install >/dev/null 2>&1 || true
        fail "The Xcode Command Line Tools are needed. An installer window should
have opened: finish it, then run this one-liner again."
    fi

    if ! command -v brew >/dev/null 2>&1; then
        local b
        for b in /opt/homebrew/bin/brew /usr/local/bin/brew; do
            [ -x "$b" ] && eval "$("$b" shellenv)" && break
        done
    fi
    command -v brew >/dev/null 2>&1 || fail "Homebrew is needed. Install it with:

  /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"

then open a new terminal window and run this one-liner again."

    if [ -d "$dir/.git" ]; then
        say "Updating the existing install in $dir"
        git -C "$dir" pull --ff-only </dev/null \
            || fail "git pull failed in $dir (did you change files there?)"
    elif [ -e "$dir" ]; then
        fail "$dir exists but isn't a ppcosxkvm checkout; move it away or set PPCOSX_HOME."
    else
        say "Downloading ppcosxkvm into $dir"
        git clone --branch "$branch" "$repo_url" "$dir" </dev/null \
            || fail "git clone failed (network?)"
    fi

    PPCOSX_INSTALLER=1 "$dir/ppcosx" setup </dev/null || fail "setup failed; see the messages above."
    "$dir/ppcosx" link </dev/null || fail "could not put ppcosx on your PATH."

    printf '\n%s✓ ppcosxkvm is installed.%s\n\n' "$G" "$N" >&2
    cat >&2 <<EOF
Next, give it Mac OS X (PowerPC). Either install from your own Tiger DVD image:

    ppcosx install ~/Downloads/MacOSX-Tiger.iso

or bring a disk you already have (.vmdk .qcow2 .vdi .img or a UTM .utm bundle):

    ppcosx import ~/VMs/Tiger.vmdk

Then boot it:

    ppcosx              (Radeon 9700, 3D acceleration)
    ppcosx --vga        (safe mode)
    ppcosx help         (everything else)

If 'ppcosx' isn't found, open a new terminal window first.
Update later with:  ppcosx update
Guide: https://github.com/linuxkid473/ppcosxkvm/blob/main/docs/GETTING-STARTED.md
EOF
}

main "$@"
