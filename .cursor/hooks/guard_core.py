"""Platform-agnostic guard predicates, shared by the Claude and Cursor adapters.

This file is the single home for every hard block in this repo. It is COPIED, verbatim and
drift-linted, into each plugin's hooks/ dir by bin/cursor-build -- it is never imported
across directories. A marketplace `directory` install resolves ${CLAUDE_PLUGIN_ROOT}
wherever it lands the plugin, so the repo root is not a reliable ancestor; a sys.path hop
would be a bet on the install layout. A copy has no runtime dependency on layout at all.

The load-bearing change from the four guards this replaces: `deny()` no longer exists.
It used to be called from inside every predicate, which welded the Claude wire format and
sys.exit into the policy logic -- so no predicate could be reused across platforms or
tested at all. Predicates now RETURN a Deny; adapters decide what a Deny means on the wire.
That is what makes hooks/test_guard_core.py possible, and these regexes had no tests.

Guard sets are per channel and composed, not inherited. laravel-workspace must NOT
get laravel-core's bare-runner block -- there are no composer scripts above the packages, so
the block would have nothing to redirect to. Composition is what lets git_tag_release exist
once while that divergence stays deliberate.
"""

import json
import os
import re
import shlex
from dataclasses import dataclass


@dataclass(frozen=True)
class Call:
    """One normalized tool call. Built by the adapter; read by the predicates.

    Construct via `shell()` or `write()` -- they own the path normalization that was
    duplicated, identically, in three of the four guards.
    """
    kind: str          # "shell" | "write"
    cwd: str
    command: str = ""  # shell
    path: str = ""     # write -- repo-relative, forward slashes, already normalized
    content: str = ""  # write -- "" means THE PLATFORM DID NOT TELL US, not "empty file"


@dataclass(frozen=True)
class Deny:
    reason: str
    rule: str   # stable id, e.g. "release-boundary". Lets ai-agents-lint assert that every
                # guard reachable on one platform is reachable on the other.


@dataclass(frozen=True)
class Ask(Deny):
    """A verdict the OPERATOR resolves, not the agent -- adapters turn it into an
    interactive prompt instead of a block.

    A subclass rather than a field on Deny so every existing construction site is
    untouched and a mistyped decision string cannot exist. `check()` treats it exactly
    like a Deny (first verdict wins); only the two adapters care about the difference.
    No guard returns it today; it stays so a verdict that is a redirect the operator can
    wave through, not a block, has a type when one is needed again.
    """


def shell(command: str, cwd: str = "") -> Call:
    return Call(kind="shell", command=command or "", cwd=cwd or os.getcwd())


def write(file_path: str, cwd: str = "", content: str = "") -> Call:
    """Normalize a write target to a repo-relative, forward-slashed path."""
    cwd = cwd or os.getcwd()
    try:
        rel = os.path.relpath(os.path.realpath(file_path), os.path.realpath(cwd))
    except ValueError:
        rel = file_path
    return Call(kind="write", path=rel.replace(os.sep, "/"), content=content or "", cwd=cwd)


# --- .dev-tools/config.json --------------------------------------------------

def _dev_tools_config(cwd):
    """The repo's .dev-tools/config.json as a dict; {} when missing, malformed or not an object.

    One plain file with no tool-specific path in it, so this needs no portability work.
    """
    try:
        with open(os.path.join(cwd, ".dev-tools", "config.json"), encoding="utf-8") as fh:
            config = json.load(fh)
    except (OSError, ValueError):
        return {}
    return config if isinstance(config, dict) else {}


def shipping_status(cwd):
    """The repo's shipping status, from the `shipped` key of .dev-tools/config.json.

    The key is the single source of truth, in BOTH tools -- for this guard, for the model (the
    `shipping-status` skill, `dt shipping`), and for `dt registry list`, which renders it as the
    Shipping column. There is no marker and no second copy.

    Only an exact JSON `false` reads as Unshipped. This fails CLOSED, deliberately: a missing
    file, a missing key, null, the string "false" or anything else gets the careful regime --
    bootstrap migrations frozen -- rather than the permissive one. An unshipped repo states so
    explicitly; silence is not permission, and a typo must not silently unlock the schema.
    """
    return "Unshipped" if _dev_tools_config(cwd).get("shipped") is False else "Shipped"


def dev_tools_type(cwd):
    """The repo's declared project type, from .dev-tools/config.json.

    Read, never inferred. The type decides which `dt` surface a repo actually has, and a
    guard that guessed it from the directory layout would point a host at a `dt workspace`
    command that does not apply to it. Anything missing, unreadable or undeclared returns ""
    -- an absent declaration is not a package.
    """
    declared = _dev_tools_config(cwd).get("type")
    return declared if isinstance(declared, str) else ""


# --- shared predicates ------------------------------------------------------

_TAG_CREATE = re.compile(
    r"\bgit\s+tag\s+"
    r"(?!-l\b|--list\b|-n|--contains\b|--no-contains\b|--points-at\b|--sort\b"
    r"|--merged\b|--no-merged\b|-d\b|--delete\b)\S"
)
_TAG_PUSH = re.compile(r"\bgit\s+push\b[^;&|]*(--tags\b|--follow-tags\b|refs/tags/|\sv\d+\.\d+)")
_GH_RELEASE = re.compile(r"\bgh\s+release\s+(create|edit|delete|upload)\b")

# The release surface, spelled the way the CLI actually spells it (`dt workspace --help`,
# `dt git --help`). `dt workspace git release` has never existed -- the workspace subcommands are
# `git commit|version|rename` plus the `patch|minor|major` shorthands for `git version` -- but the
# name stays matched so a future alias cannot open a hole. `:laravel` / `:frontend` stack suffixes
# are accepted because `dt workspace:laravel git version` is the same command.
#
# `rewire` is that same pipeline with a headless session inserted before ci, so it commits, tags
# and pushes every package in the workspace and belongs here. Its read-only `--plan` is swept up
# with it deliberately: a carve-out would have to be right about where the flag sits in the line,
# and being wrong about that reopens the whole release surface to save the operator one command.
WORKSPACE_RELEASE_RE = (
    r"\bdt\s+workspace(?::\w+)?\s+((git\s+)?(version|release)|patch|minor|major|rewire)\b"
)
TOOLKIT_RELEASE_RE = (
    r"\bdt\s+(git\s+(version|release|github-release)|patch|minor|major)\b"
)


def git_tag_release(call):
    """Tag creation and GitHub releases are operator-only. Reads stay allowed.

    This block used to exist in THREE copies -- laravel-core, frontend-core, and
    laravel-workspace -- each carrying a comment saying "There is no mechanism to
    consolidate these -- do not try." That was true when a plugin could not import another.
    Copying the core into every plugin is the mechanism. It reached three copies while the
    comment said not to fix it, which is the argument, not against it.
    """
    if call.kind != "shell":
        return None
    c = call.command
    if _TAG_CREATE.search(c) or _TAG_PUSH.search(c) or _GH_RELEASE.search(c):
        return Deny(
            "Blocked: creating a tag or a GitHub release is operator-only. Say which "
            "command the user should run and stop. Reading tags is fine (`git tag -l`).",
            rule="release-boundary-tags",
        )
    return None


def composer_release(call):
    """`composer version:*|release` and the workspace orchestrator's release."""
    if call.kind != "shell":
        return None
    if re.search(r"\bcomposer\s+(version:(patch|minor|major)|release)\b", call.command) \
       or re.search(WORKSPACE_RELEASE_RE, call.command) \
       or re.search(TOOLKIT_RELEASE_RE, call.command):
        return Deny(
            "Blocked: version bumps and releases are operator-only. Say which command "
            "the user should run and stop.",
            rule="release-boundary-composer",
        )
    return None


def npm_release(call):
    if call.kind != "shell":
        return None
    if re.search(r"\bnpm\s+(version|publish)\b", call.command):
        return Deny(
            "Blocked: version bumps and publishes are operator-only. Say which command "
            "the user should run and stop.",
            rule="release-boundary-npm",
        )
    return None


# --- coding-core ------------------------------------------------------------

# A numbered release heading. `## [Unreleased]` is deliberately NOT matched -- writing
# bullets under it is ordinary work, and it is the only changelog edit an agent makes.
RELEASE_HEADING = re.compile(r"^##\s*\[?v?\d+\.\d+\.\d+", re.M)
# A semver `version` field in a manifest. Everything else in the file stays editable.
VERSION_FIELD = re.compile(r'"version"\s*:\s*"v?\d+\.\d+\.\d+')


def version_write(call):
    """The file-write half of release-boundary. The shell half blocks the release COMMANDS;
    this blocks writing their OUTPUT by hand, which achieves the same thing and did.

    Scoped to files that ALREADY EXIST, which is what keeps `scaffold` working -- a new
    package legitimately writes `VERSION` 0.1.0 and a fresh composer.json. The harm is
    bumping, not creating. CHANGELOG.md needs no such check: a fresh changelog carries only
    `## [Unreleased]`, so the heading pattern cannot fire on one.

    Why a guard and not the rule alone: `promote_changelog_unreleased` in dev-tools returns
    SUCCESS and changes nothing when `## [<ver>]` is already present, so an invented heading
    makes the operator's next real bump skip promotion SILENTLY and strand the notes.
    """
    if call.kind == "shell":
        return _version_shell_write(call)
    if call.kind != "write":
        return None
    name = call.path.rsplit("/", 1)[-1]

    if name == "CHANGELOG.md":
        if not RELEASE_HEADING.search(call.content):
            return None
    elif name == "VERSION":
        if not os.path.exists(os.path.join(call.cwd, call.path)):
            return None
    elif name in ("composer.json", "package.json"):
        if not VERSION_FIELD.search(call.content):
            return None
        if not os.path.exists(os.path.join(call.cwd, call.path)):
            return None
    else:
        return None

    return _version_write_deny()


def _version_write_deny():
    return Deny(
        "Blocked: version numbers are operator-only. `dt patch|minor|major` derives "
        "the next number from VERSION and writes the heading, the date, VERSION and the manifest's "
        "`version` field itself. A number written by hand names a release that does not "
        "exist, and the operator's next real bump then skips promotion silently. Add "
        "bullets under `## [Unreleased]` and stop; say which command the user should run.",
        rule="release-boundary-version-write",
    )


# `VERSION` as a file name: not `APP_VERSION`, not `VERSION.md`.
_VFILE = r"(?<![\w.-])(?:[\w./~-]*/)?VERSION(?![\w.-])"
# Writes into VERSION from a shell command, or from a script body the command runs.
_VERSION_SHELL_WRITES = [re.compile(p, re.M) for p in (
    r">>?\s*['\"]?" + _VFILE,                                              # > VERSION
    r"\btee\b(?:\s+-\S+)*\s+['\"]?" + _VFILE,                              # tee [-a] VERSION
    r"\b(?:sed|gsed|perl)\b(?=[^;&|\n]*\s-[a-zA-Z]*i)[^;&|\n]*" + _VFILE,  # sed -i … VERSION
    r"\b(?:cp|mv|install|truncate)\b[^;&|\n]*\s['\"]?" + _VFILE + r"['\"]?\s*(?:$|[;&|)])",
    r"open\(\s*[rbuf]?['\"](?:[^'\"\n]*/)?VERSION['\"]\s*,\s*[rbuf]?['\"][^'\"]*[wax+]",
    r"VERSION['\"]\s*\)\s*\.write_(?:text|bytes)\(",                       # Path(…).write_text
    r"(?:file_put_contents|writeFileSync|writeFile)\(\s*[^,\n]*VERSION['\"]",
)]
# (file named, release text present) -- in a text that also writes files. Order-free: a heredoc
# names the file first, `sed -i 's/…/…/' package.json` names it last.
_RELEASE_TEXT_SHELL = [(re.compile(f), re.compile(t)) for f, t in (
    (r"CHANGELOG\.md", r"##\s*\[?v?\d+\.\d+\.\d+"),
    (r"(?:composer|package)\.json", r"\"version\\?\"\s*:\s*\\?\"v?\d+\.\d+\.\d+"),
)]
# Gates _RELEASE_TEXT_SHELL so `grep '## \[1.2.0\]' CHANGELOG.md` and `cat package.json` pass.
_WRITE_HINT = re.compile(
    r"open\([^)]*['\"][^'\"]*[wa+]['\"]|\.write\(|write_text\(|write_bytes\(|file_put_contents\("
    r"|writeFileSync\(|writeFile\(|>>?\s*[\w./~'\"-]|\btee\b|\b(?:sed|perl)\b[^;&|\n]*\s-[a-zA-Z]*i"
)
# `python3 x.py`, `php x.php`, `node x.js`, `bash x.sh`, … -- the script body is scanned too.
_SCRIPT_RUN = re.compile(
    r"\b(?:python3?|php|node|bash|sh|perl|ruby)\s+(?:-\S+\s+)*['\"]?"
    r"([^\s;&|<>'\"]+\.(?:py|php|js|mjs|cjs|sh|pl|rb))"
)


def _version_shell_write(call):
    """The shell half of version_write: the same three writes, made through Bash instead of
    the Write/Edit tools. Without it the file-write half is advisory -- `open('VERSION','w')`
    in a `python3 script.py` body went straight past it, in two packages, in one session.

    Unlike the file-write half this does not exempt a VERSION that does not exist yet:
    resolving the target through `cd` chains is guesswork, and scaffolding writes VERSION
    through `dt`, whose command line names no VERSION write. A script run by relative path
    resolves against the hook's cwd only; one reached through `cd` is not scanned.
    """
    texts = [call.command]
    for script in _SCRIPT_RUN.findall(call.command):
        path = os.path.expanduser(script)
        if not os.path.isabs(path):
            path = os.path.join(call.cwd, path)
        try:
            if os.path.getsize(path) <= 1_000_000:
                with open(path, encoding="utf-8", errors="replace") as fh:
                    texts.append(fh.read())
        except OSError:
            pass

    for text in texts:
        if any(p.search(text) for p in _VERSION_SHELL_WRITES):
            return _version_write_deny()
        if _WRITE_HINT.search(text) and any(f.search(text) and t.search(text)
                                            for f, t in _RELEASE_TEXT_SHELL):
            return _version_write_deny()
    return None


# --- laravel-core -----------------------------------------------------------

def bare_runners(call):
    """Bare runners skip the setup the composer scripts do, and the scripts are what CI runs.

    Deliberately does NOT match `composer test|stan|lint` -- the sanctioned paths do not
    contain these literal strings. test_guard_core.py pins that, because a guard that denies
    `composer test` makes the whole channel unusable and a positive-only test would pass.
    """
    if call.kind != "shell":
        return None
    if re.search(r"\bvendor/bin/(pest|phpunit|pint|phpstan)\b", call.command) \
       or re.search(r"(^|[;&|]\s*)phpunit\b", call.command):
        return Deny(
            "Blocked: this bypasses the setup the composer scripts do, and the "
            "scripts are what CI runs. Use `composer test` / `composer stan` / "
            "`composer lint` (filter tests with `composer test -- --filter Name`).",
            rule="bare-runners",
        )
    return None


def generated_openapi(call):
    if call.kind != "write":
        return None
    if re.search(r"(^|/)docs/openapi/openapi\.ya?ml$", call.path):
        return Deny(
            "Blocked: docs/openapi/openapi.yaml is generated -- an edit here is "
            "overwritten by the next build. Edit the sources under docs/openapi/ and "
            "run `composer dev openapi merge` (a host can run `composer dev openapi "
            "all` to lint and audit in the same pass).",
            rule="generated-openapi",
        )
    return None


def frozen_bootstrap_migrations(call):
    """Bootstrap `{AAAA}_*` migrations freeze once the repo reads as Shipped."""
    if call.kind != "write":
        return None
    if not re.match(r"^database/migrations/", call.path):
        return None
    if shipping_status(call.cwd) != "Shipped":
        return None
    base = os.path.basename(call.path)
    if not (re.match(r"^\d{4}_", base) and not re.match(r"^20\d{2}_", base)):
        return None
    # Name the missing key when that is the cause. Absence reads as Shipped, so without
    # this the block looks like a wrong verdict rather than a wrong repo.
    if "shipped" not in _dev_tools_config(call.cwd):
        return Deny(
            f"Blocked: this repo has no `shipped` key in .dev-tools/config.json, which reads "
            f"as Shipped, so bootstrap migrations are frozen. `{base}` is a bootstrap "
            f"`{{AAAA}}_*` migration. If this repo is pre-production, add `\"shipped\": false` "
            f"to .dev-tools/config.json (`dt shipping` prints the reading). If it is live, "
            f"create a dated migration instead. See the `shipping-status` skill.",
            rule="frozen-bootstrap-migrations",
        )
    return Deny(
        f"Blocked: this repo is Shipped, so bootstrap migrations are frozen. `{base}` is a "
        f"bootstrap `{{AAAA}}_*` migration. Create a dated migration instead. See the "
        f"`shipping-status` skill.",
        rule="frozen-bootstrap-migrations",
    )


# --- laravel-host -------------------------------------------------------

def artisan_test(call):
    """Host-only: packages have no artisan, they run on Testbench."""
    if call.kind != "shell":
        return None
    if re.search(r"(^|[;&|]\s*|\bexec\s+\w+\s+)php\s+artisan\s+test\b", call.command):
        return Deny(
            "Blocked: this bypasses test isolation. Use `composer test` from the repo "
            "root (filter with `composer test -- --filter=Name`). It starts the test "
            "database, clears config cache, and applies the isolation env vars that "
            "`php artisan test` skips. See docs/reference/testing-isolation.md.",
            rule="artisan-test",
        )
    return None


# --- frontend-core ---------------------------------------------------------

def generated_css(call):
    """The token generators emit BOTH stylesheets and a TS module, so match on the
    `.generated.` marker rather than the extension -- a host's `colors-hex.generated.ts` is
    overwritten by the same command that overwrites its `theme-colors.generated.css`."""
    if call.kind != "write":
        return None
    if re.search(r"\.generated\.(css|ts)$", call.path):
        return Deny(
            "Blocked: this file is generated from the design tokens. Edit the source and "
            "run its generator: a colour in the host's `brands/semantic-colors.json`, then "
            "`npm run generate:theme` there; the spacing or type scale in `@aragusnz/utils` "
            "`src/tokens/scale.json`, then `npm run generate:css` in that repo.",
            rule="generated-css",
        )
    return None


def platform_bleed(call):
    """Tailwind and the `@/` alias are web-only and always a bug in React Native code.

    Two shapes carry that code: `apps/mobile/` in a host, and `src/mobile/` in a module
    package repo. Both are matched by path because both are unambiguously the mobile half
    of a repo that also holds web code.

    `src/mobile/` also covers the mobile kit, which lives in `@aragusnz/utils` beside the web
    kit. Widening this predicate to every `src/` would deny className in every web package.

    Content-based: the file path alone cannot reveal it. `not call.content` is the
    platform-did-not-tell-us case, and it must not be read as an empty file -- absent
    content means we have nothing to judge, so we allow rather than block blind.
    """
    if call.kind != "write" or not call.content:
        return None
    if not (call.path.startswith("apps/mobile/") or call.path.startswith("src/mobile/")):
        return None
    if re.search(r'className\s*=\s*["\'{]', call.content):
        return Deny(
            "Blocked: `className` is web-only. This is React Native — use StyleSheet "
            "with design tokens, and MobileButton/TextField from @aragusnz/utils/mobile. "
            "A Tailwind class in mobile code is always a bug.",
            rule="platform-bleed-classname",
        )
    if re.search(r'from\s+["\']@/', call.content) or re.search(r'import\s+["\']@/', call.content):
        return Deny(
            "Blocked: the `@/` alias does not exist in mobile code. Use a relative "
            "import, or `@aragusnz/*` for shared packages.",
            rule="platform-bleed-alias",
        )
    return None


# --- laravel-workspace ----------------------------------------------

def workspace_write(call):
    """`dt workspace git release|commit` write across every package repo in dependency order."""
    if call.kind != "shell":
        return None
    # `git` is optional so the pre-regroup bare form stays denied too, and `release` stays
    # matched although the CLI has no such subcommand -- a future alias must not open a hole.
    if re.search(WORKSPACE_RELEASE_RE, call.command) \
       or re.search(r"\bdt\s+workspace(?::\w+)?\s+(git\s+)?commit\b", call.command):
        return Deny(
            "Blocked: `dt workspace git version` (and its `patch|minor|major` shorthands) and "
            "`dt workspace git commit` are operator-only -- they write across every package repo "
            "in dependency order. Say which command the user should run and stop.",
            rule="release-boundary-workspace",
        )
    if re.search(TOOLKIT_RELEASE_RE, call.command):
        return Deny(
            "Blocked: `dt git version|release` and the `dt patch|minor|major` "
            "shorthands are operator-only -- they tag and release a single repo. Say which "
            "command the user should run and stop.",
            rule="release-boundary-toolkit",
        )
    return None


def per_package_release_at_root(call):
    """The per-package release commands, run from the root, name the wrong procedure."""
    if call.kind != "shell":
        return None
    if re.search(r"\bcomposer\s+(version:(patch|minor|major)|release)\b", call.command) \
       or re.search(r"\bnpm\s+(version|publish)\b", call.command):
        return Deny(
            "Blocked: version bumps and releases are operator-only. For workspace-wide work "
            "the command is `dt workspace git version`, not the per-package one -- say which "
            "the user should run and stop.",
            rule="release-boundary-workspace-per-package",
        )
    return None


def cross_repo_git(call):
    if call.kind != "shell":
        return None
    if re.search(r"\bgit\s+-C\s+\S+\s+(commit|push|tag|reset\s+--hard)\b", call.command) \
       or re.search(r"\bfor\b[^;]*\bin\b[^;]*\*/[^;]*;[^;]*\bgit\b[^;]*\b(commit|push)\b", call.command):
        return Deny(
            "Blocked: cross-repo commits from the workspace root. Each package folder is its "
            "own repo -- a root commit never covers a package change. Name the repo that owns "
            "the change and let the user commit it there.",
            rule="cross-repo-git",
        )
    return None


# --- global -----------------------------------------------------------------
# Not a channel guard. Wired once in ~/.claude/settings.json via hooks/rm_scope_guard.py, so
# it also covers ~ and unwired checkouts -- which is where an unscoped rm does the damage.

_SEPARATORS = {";", "&&", "||", "|", "&"}
_RUNTIME_EXPANSION = re.compile(r"[$`]")


def rm_scope(call):
    """`rm` is ordinary work inside the project; outside it the operator decides.

    Returns "allow" or None -- never a Deny. "allow" when every target resolves inside the
    project; None for everything else, which falls through to the normal permission prompt.
    Two states, not the Deny|None contract `check()` expects, so this sits outside GUARD_SETS
    and gets its own adapter. That is also why ai-agents-lint's plugin/GUARD_SETS parity is
    untouched: this guard has no channel.

    The ALLOW verdict is the load-bearing part. It replaces the blanket `Bash(rm -rf *)` deny
    that used to sit in permissions.deny, and it lives here rather than in permissions.allow
    on purpose: a hook that is missing, broken, or raising exits 0, so rm degrades to the
    normal permission prompt. An allow rule in settings would have degraded to silently
    permitted instead.

    ponytail: a token walk, not a shell parser. `rm` is only recognised in command position,
    so `xargs rm`, `find -exec rm`, and `sudo rm` fall through to the prompt rather than being
    judged; `$VAR` targets, unparseable quoting, out-of-project targets and the checkout root
    itself all land on the prompt too. Every unhandled shape lands on "prompt", never on
    "allow". Reach for bashlex only if that ever bites.
    """
    if call.kind != "shell" or not re.search(r"\brm\b", call.command):
        return None

    root = os.path.realpath(os.environ.get("CLAUDE_PROJECT_DIR") or call.cwd)
    if root == os.path.sep or root == os.path.realpath(os.path.expanduser("~")):
        return None  # no project boundary to be inside of -- prompt

    # A project may name sibling checkouts it is allowed to delete inside -- set per project,
    # never globally, so an unwired checkout keeps the plain project boundary.
    roots = [root, *(
        os.path.realpath(os.path.expanduser(p))
        for p in os.environ.get("RM_SCOPE_EXTRA_ROOTS", "").split(os.pathsep) if p
    )]

    cwd, targets = os.path.realpath(call.cwd), 0
    for line in call.command.splitlines():
        try:
            tokens = shlex.split(line, comments=True)
        except ValueError:
            return None  # cannot parse safely -- prompt
        mode, end_of_flags = "cmd", False
        for token in tokens:
            if token in _SEPARATORS:
                mode, end_of_flags = "cmd", False
            elif mode == "cmd":
                mode = {"rm": "rm", "cd": "cd"}.get(token, "args")
            elif mode == "cd":
                cwd = os.path.realpath(os.path.join(cwd, os.path.expanduser(token)))
                mode = "args"
            elif mode == "rm":
                if token == "--":
                    end_of_flags = True
                elif not end_of_flags and token.startswith("-"):
                    pass
                elif not _rm_target_inside(token, cwd, roots):
                    return None
                else:
                    targets += 1

    # `rm` matched the regex but no target resolved -- an unhandled shape. Fall through to the
    # normal permission prompt rather than guessing.
    return "allow" if targets else None


# One topic file in a repo's own TODO folder, which may be another repo's. The standing exception
# in the `workspace-boundary` rule already lets any session write these; `todo-location` tells it
# to delete the file once its last item goes, so the delete has to be reachable too. Narrow on
# purpose: one `.md` leaf directly under `todo/`. The folder itself, the `config.json` beside it,
# `actions/`, and everything else in `.dev-tools/` stay on the ordinary boundary check.
_REPO_TODO_FILE = re.compile(r"/\.dev-tools/todo/[^/]+\.md$")


def _rm_target_inside(token, cwd, roots):
    """True if this `rm` target sits inside some root in `roots` (or is a repo TODO file).
    realpath, so a symlink out of the project (a path-repository under vendor/, a workspace
    link under node_modules/) resolves to where it actually points. `roots[0]` is the project
    itself; any others came from RM_SCOPE_EXTRA_ROOTS. A root itself is not inside it -- naming
    the checkout root is the whole-repo mistake, wherever it sits. Runtime expansion (`$VAR`,
    backticks) cannot be resolved, so it is not inside either."""
    if _RUNTIME_EXPANSION.search(token):
        return False
    target = os.path.realpath(os.path.join(cwd, os.path.expanduser(token)))
    if _REPO_TODO_FILE.search(target):
        return True
    return any(target.startswith(root + os.sep) for root in roots)


# --- stash discipline --------------------------------------------------------
# In EVERY channel's guard set AND wired globally (~/.claude/settings.json via
# hooks/git_guard.py), so unwired checkouts are covered too. Double coverage in a wired
# project is harmless -- same predicate, same verdict. Unlike rm_scope this returns only
# Deny|None, which is what makes GUARD_SETS membership safe: check() reads any non-None
# as a Deny.

_GIT_VALUE_FLAGS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace"}


def stash_discipline(call):
    """The stash list is shared mutable state across every agent in a checkout.

    An anonymous `git stash` cannot be recalled by name, and a bare `git stash pop` grabs
    whatever is on top -- possibly another agent's work. So: push must carry a message,
    pop/apply/drop must name an explicit ref, and `clear` (which wipes everyone's entries)
    is denied outright. `list`/`show` and non-stash git stay untouched.

    ponytail: a token walk like rm_scope, not a shell parser. `sudo git stash` and aliases
    fall through to the normal prompt; nothing unhandled lands on a quiet pass-through of a
    stash write.
    """
    if call.kind != "shell" or "stash" not in call.command:
        return None
    for line in call.command.splitlines():
        if "stash" not in line or "git" not in line:
            continue
        try:
            tokens = shlex.split(line, comments=True)
        except ValueError as exc:
            return Deny(
                f"Blocked: this command touches `git stash` and could not be parsed safely "
                f"({exc}). Split it into simpler commands.",
                rule="stash-discipline",
            )
        for args in _stash_invocations(tokens):
            verdict = _stash_verdict(args)
            if verdict:
                return verdict
    return None


def _stash_invocations(tokens):
    """Yield the argument list of each `git [flags] stash …` invocation in `tokens`."""
    mode, skip_value, current = "cmd", False, None
    for token in tokens:
        if token in _SEPARATORS:
            if current is not None:
                yield current
            mode, skip_value, current = "cmd", False, None
        elif current is not None:
            current.append(token)
        elif mode == "cmd":
            mode = "git" if token == "git" else "args"
        elif mode == "git":
            if skip_value:
                skip_value = False
            elif token == "stash":
                current = []
            elif token in _GIT_VALUE_FLAGS:
                skip_value = True
            elif token.startswith("-"):
                pass
            else:
                mode = "args"
    if current is not None:
        yield current


def _stash_verdict(args):
    action, rest = "push", args
    if args and not args[0].startswith("-"):
        action, rest = args[0], args[1:]
    if action == "clear":
        return Deny(
            "Blocked: `git stash clear` deletes every stash in this checkout, including "
            "other agents' work. Drop your own entries one at a time, by ref.",
            rule="stash-discipline",
        )
    if action in ("pop", "apply", "drop"):
        if any(t and not t.startswith("-") for t in rest):
            return None
        return Deny(
            f"Blocked: `git stash {action}` with no stash ref acts on whatever is on top -- "
            f"possibly another agent's stash. Run `git stash list`, find YOUR named entry, "
            f"then name that exact ref: `git stash {action} 'stash@{{n}}'` or "
            f"`git stash apply 'stash^{{/<slug>}}'`.",
            rule="stash-discipline",
        )
    if action in ("push", "save") and not _stash_named(action, rest):
        return Deny(
            "Blocked: unnamed stash. Agents share this checkout's stash list, and an "
            "anonymous entry cannot be recalled by name. Use "
            '`git stash push -m "<task-slug>"`.',
            rule="stash-discipline",
        )
    return None


def _stash_named(action, rest):
    if action == "save":
        return any(t and not t.startswith("-") for t in rest)
    prev = None
    for token in rest:
        if token.startswith("--message=") and len(token) > len("--message="):
            return True
        if prev in ("-m", "--message") and token:
            return True
        prev = token
    return False


# --- branch discipline -------------------------------------------------------
# Same wiring as stash discipline: project-core's set AND the global hooks/git_guard.py, so
# unwired checkouts are covered. Deny|None only, so GUARD_SETS membership is safe.

_GIT_BRANCH_CMD = re.compile(
    r"(?:^|[;&|(\n]|\bdo\b|\bthen\b)\s*git\b((?:\s+(?:-C|-c|--git-dir|--work-tree|--namespace)\s+\S+|\s+-\S+)*)"
    r"\s+(checkout|switch|branch|worktree)\b([^;&|\n]*)"
)
_BRANCH_VALUE_FLAGS = {"--contains", "--no-contains", "--merged", "--no-merged",
                       "--points-at", "--sort", "--format", "--column", "-u",
                       "--set-upstream-to"}


def branch_discipline(call):
    """Agents work on the branch they were started on. Creating, renaming, copying,
    deleting or switching branches is the operator's call -- and Claude Code's built-in
    'branch first on the default branch' advice is exactly what this overrides.

    Denies `checkout -b/-B/--orphan`, any `switch`, `branch` with a name or -m/-c,
    and `worktree add` without `--detach` (it creates a branch). Listing stays allowed:
    `git branch`, `git branch -a`, `--show-current`, `--list <pattern>`.

    ponytail: a regex over the raw command, not a shell parse. `git` counts only in command
    position (line start, after ; & | ( do then) -- so it sees `git -C $p …` inside a
    `for … do` loop, which the stash token walk misses, and skips `grep 'git switch'`.
    Ceiling: a quoted string or heredoc line that itself starts a command (`"x; git switch"`)
    is denied too.
    """
    if call.kind != "shell" or "git" not in call.command:
        return None
    for match in _GIT_BRANCH_CMD.finditer(call.command):
        sub, args = match.group(2), match.group(3).split()
        if _branch_change(sub, args):
            shown = " ".join(["git", sub, *args])
            return Deny(
                f"Blocked: `{shown}` changes branches. Agents work "
                f"and commit on the CURRENT branch, whatever it is -- including main. Do not "
                f"create, switch, rename or delete a branch, and do not hand the operator a "
                f"command that does. If the work truly needs a branch, stop and ask.",
                rule="branch-discipline",
            )
    return None


def _branch_change(sub, args):
    if sub == "switch":
        return True
    if sub == "checkout":
        return any(a in ("-b", "-B", "--orphan") or a.startswith("--orphan=") for a in args)
    if sub == "worktree":
        if not args or args[0] != "add":
            return False
        detached = "--detach" in args or "-d" in args
        return not detached or "-b" in args or "-B" in args
    # sub == "branch"
    if any(a in ("-m", "-M", "-c", "-C", "--move", "--copy") for a in args):
        return True
    if any(a in ("-l", "--list", "--show-current") for a in args):
        return False
    skip = False
    for a in args:
        if skip:
            skip = False
        elif a in _BRANCH_VALUE_FLAGS:
            skip = True
        elif not a.startswith("-") and not a.startswith((">", "2>")):
            return True
    return False


# --- legals: signed and received documents ---------------------------------

_LEGALS_RECORD_PATH = re.compile(r"(^|/)(executed|incoming)/[^/]+$")
# Mutating shell forms aimed at a record path. `cp incoming/x agreements/` is the normal way a
# redline starts and stays allowed: only the source is a record, and cp does not touch it.
_LEGALS_RECORD_SHELL = re.compile(
    r"(?:\b(?:rm|mv|sed\s+-i\S*|truncate|tee)\b[^;&|\n]*|>>?\s*)"
    r"(?:\S*/)?(?:executed|incoming)(?:/\S*)?(?=\s|$|[;&|)])"
)


def legals_readonly_records(call):
    """A signed agreement or a counterparty's draft as received is a record, never a draft.

    `agreements/<matter>/executed/` holds what was signed; `incoming/` holds what the other
    side sent. Both are evidence of what the parties actually agreed or proposed, and an edit
    there -- even a tidy-up -- destroys the one copy that proves it. A correction is a deed of
    variation; a redline is a marked copy under agreements/. Writes and the common mutating
    shell forms are denied; reads and `cp` FROM a record stay open.

    ponytail: regex over the raw command, not a shell parse; a runtime-expanded path
    (`rm $f`) is not seen. Upgrade to a token walk if that ever bites.
    """
    if call.kind == "write":
        if _LEGALS_RECORD_PATH.search(call.path):
            return Deny(
                f"Blocked: `{call.path}` is a record -- a signed agreement under executed/ or a "
                f"counterparty's draft under incoming/ -- and is never edited. A redline is a "
                f"marked copy under agreements/<matter>/; a correction to a signed agreement is "
                f"a deed of variation.",
                rule="legals-readonly-records",
            )
        return None
    if call.kind == "shell" and ("executed" in call.command or "incoming" in call.command):
        match = _LEGALS_RECORD_SHELL.search(call.command)
        if match:
            return Deny(
                f"Blocked: `{match.group(0).strip()}` modifies a record under executed/ or "
                f"incoming/. Those are never changed, moved or removed by an agent -- copy "
                f"out of them into agreements/<matter>/ instead.",
                rule="legals-readonly-records",
            )
    return None


# --- guard sets -------------------------------------------------------------
# Per unit, composed. Every unit in a project's stack is enabled at once and PreToolUse
# hooks compose, so a predicate belongs in the LOWEST unit where it is universally true --
# stated once there rather than repeated in each set above it. Adding a unit means adding a
# set here; the emitter and the parity lint both read this dict, so a unit with no set is
# loud rather than silent.
#
# The stack a project gets is `project-core` + the channel's declared `bases` + the channel
# (see units_of() in dev-tools' cmd/agents/py/_config_lib.py). Every entry below is reachable
# from every channel that needs it, by construction.

GUARD_SETS = {
    # Enabled in every wired project, whatever its channel. `stash_discipline` was repeated
    # in all five sets below; the stash list is shared mutable state in any repo, code or not.
    "project-core": [
        stash_discipline,
        branch_discipline,
    ],
    # Every code channel, Laravel and frontend alike. `git_tag_release` was repeated in four
    # sets: tagging is operator-only in any code repo, and the rule that says so
    # (release-boundary) lives in this layer too.
    "coding-core": [
        git_tag_release,
        version_write,
    ],
    "laravel-core": [
        bare_runners,
        composer_release,
        generated_openapi,
        frozen_bootstrap_migrations,
    ],
    "laravel-host": [
        artisan_test,
    ],
    "frontend-core": [
        npm_release,
        generated_css,
        platform_bleed,
    ],
    "frontend-workspace": [
        npm_release,
        cross_repo_git,
    ],
    "laravel-workspace": [
        workspace_write,
        per_package_release_at_root,
        cross_repo_git,
    ],
    # No base: a legals repo is documents, not code. The one hard block is the record
    # folders -- a signed agreement or a counterparty's draft as received is evidence.
    "legals": [
        legals_readonly_records,
    ],
}


def check(call, guards):
    """First Deny wins. None means nothing objected -- NOT that the call is approved;
    it proceeds through the platform's normal permission flow."""
    for guard in guards:
        verdict = guard(call)
        if verdict is not None:
            return verdict
    return None


# --- platform adapters ------------------------------------------------------
# The only platform-specific code in this file. Each plugin's guard.py is three lines that
# call one of these with its channel name -- there is no fifth copy of the payload parsing.
#
# ON FAILING OPEN. Both adapters catch Exception and let the call through, loudly, on stderr.
# That is deliberate and it is the mitigation for the plan's highest-damage risk: this file is
# copied into ~5 plugins across 33 repos, and on Cursor it runs with failClosed: true. Without
# the catch, one bad payload shape or one traceback denies EVERY write in EVERY session --
# a fleet-wide lockout from a typo. The existing guards already took this position for
# malformed JSON ("never break the session on a malformed payload"); this generalises it.
#
# The two mechanisms cover different failures and you need both: failClosed catches the hook
# not RUNNING; this catches it running BADLY. A guard that crashes is a guard that is absent,
# and an absent guard should be noisy, not fatal.


def _emit_and_exit(payload, code=0):
    import json as _json
    import sys as _sys
    _json.dump(payload, _sys.stdout)
    _sys.exit(code)


def _fail_open(exc, platform):
    import sys as _sys
    import traceback as _tb
    print(f"guard_core: {platform} adapter raised, failing OPEN -- {exc!r}", file=_sys.stderr)
    _tb.print_exc(file=_sys.stderr)
    _sys.exit(0)


def claude_main(channel):
    """PreToolUse adapter. Reads Claude's payload; emits hookSpecificOutput."""
    import json as _json
    import sys as _sys
    try:
        try:
            payload = _json.load(_sys.stdin)
        except (_json.JSONDecodeError, ValueError):
            _sys.exit(0)  # never break the session on a malformed payload

        tool = payload.get("tool_name", "")
        ti = payload.get("tool_input") or {}
        cwd = payload.get("cwd") or os.getcwd()

        if tool == "Bash":
            call = shell(ti.get("command", "") or "", cwd)
        elif tool in ("Edit", "Write", "NotebookEdit"):
            fp = ti.get("file_path") or ti.get("notebook_path") or ""
            if not fp:
                _sys.exit(0)
            # Write sends `content`; Edit sends `new_string`.
            call = write(fp, cwd, ti.get("content") or ti.get("new_string") or "")
        else:
            _sys.exit(0)

        verdict = check(call, GUARD_SETS.get(channel, []))
        if verdict:
            _emit_and_exit({"hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask" if isinstance(verdict, Ask) else "deny",
                "permissionDecisionReason": verdict.reason,
            }})
        _sys.exit(0)
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 -- see ON FAILING OPEN above
        _fail_open(exc, "claude")


def claude_rm_main():
    """PreToolUse adapter for the global rm-scope guard. Bash only, allow or silence.

    Separate from claude_main because this one emits ALLOW. claude_main only ever denies --
    silence there means "nothing objected", which is not the same as "approved". Here silence
    means "the operator decides" (the normal permission prompt) and the wire has to say which.
    """
    import json as _json
    import sys as _sys
    try:
        try:
            payload = _json.load(_sys.stdin)
        except (_json.JSONDecodeError, ValueError):
            _sys.exit(0)  # never break the session on a malformed payload

        if payload.get("tool_name") != "Bash":
            _sys.exit(0)

        command = (payload.get("tool_input") or {}).get("command", "") or ""
        if rm_scope(shell(command, payload.get("cwd") or os.getcwd())) != "allow":
            _sys.exit(0)

        _emit_and_exit({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "permissionDecisionReason": "Every `rm` target resolves inside the project.",
        }})
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 -- see ON FAILING OPEN above
        _fail_open(exc, "claude-rm")


def claude_git_main():
    """PreToolUse adapter for the global git guard (hooks/git_guard.py). Deny-only.

    Wired in ~/.claude/settings.json with matcher `Bash|Agent`, so stash and branch
    discipline hold in ~ and unwired checkouts. In a wired project project-core's guard.py
    carries the same Bash predicates; the verdicts agree, so the overlap is harmless.
    Agent is here because `isolation: "worktree"` makes a worktree-* branch.
    """
    import json as _json
    import sys as _sys
    try:
        try:
            payload = _json.load(_sys.stdin)
        except (_json.JSONDecodeError, ValueError):
            _sys.exit(0)  # never break the session on a malformed payload

        tool = payload.get("tool_name")
        ti = payload.get("tool_input") or {}
        verdict = None
        if tool == "Bash":
            call = shell(ti.get("command", "") or "", payload.get("cwd") or os.getcwd())
            verdict = check(call, [stash_discipline, branch_discipline])
        elif tool == "Agent" and ti.get("isolation") == "worktree":
            verdict = Deny(
                "Blocked: `isolation: \"worktree\"` creates a branch. Agents work on the "
                "current branch -- run the subagent without isolation.",
                rule="branch-discipline",
            )
        if verdict:
            _emit_and_exit({"hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": verdict.reason,
            }})
        _sys.exit(0)
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 -- see ON FAILING OPEN above
        _fail_open(exc, "claude-git")


def guards_for(channels):
    """The composed guard list for one or more channels, order-preserving and de-duplicated.

    Cursor has ONE .cursor/hooks.json per project, so a wired project passes its base AND its
    channel here (e.g. laravel-core laravel-host) and both guard sets run from a single
    invocation. De-dup matters because git_tag_release is in three sets; without it a project
    on a channel that also carries it would run it twice.
    """
    seen, out = set(), []
    for ch in channels:
        for guard in GUARD_SETS.get(ch, []):
            if guard not in seen:
                seen.add(guard)
                out.append(guard)
    return out


def cursor_main(*channels):
    """Cursor adapter for preToolUse and beforeShellExecution. Channels come from argv.

    Two payload differences from Claude, both load-bearing:
      - beforeShellExecution puts `command` at the TOP LEVEL, not under tool_input.
      - the deny shape is {"permission": "deny"}, and blocking wants exit code 2.

    Shell guards route through beforeShellExecution rather than preToolUse+matcher Shell:
    it is the narrower documented event, it supports "ask", and -- the reason that decides
    it -- the open reports of deny being ignored are specifically about preToolUse on Write.
    The spike confirmed deny IS honoured for Write on this platform, but the split costs
    nothing and keeps the shell blocks off the historically contested path.
    """
    import json as _json
    import sys as _sys
    try:
        try:
            payload = _json.load(_sys.stdin)
        except (_json.JSONDecodeError, ValueError):
            _sys.exit(0)

        event = payload.get("hook_event_name") or payload.get("event") or ""
        cwd = payload.get("cwd") or (payload.get("workspace_roots") or [None])[0] or os.getcwd()

        if event == "beforeShellExecution" or payload.get("command"):
            call = shell(payload.get("command") or "", cwd)
        else:
            ti = payload.get("tool_input") or payload
            fp = ti.get("file_path") or ti.get("path") or ""
            if not fp:
                _sys.exit(0)
            call = write(fp, cwd, ti.get("content") or ti.get("new_string") or "")

        verdict = check(call, guards_for(channels))
        if isinstance(verdict, Ask):
            # `ask` is why the shell guards route through beforeShellExecution -- see above.
            _emit_and_exit({
                "permission": "ask",
                "agent_message": verdict.reason,
                "user_message": f"{verdict.rule}: needs your say-so",
            })
        if verdict:
            _emit_and_exit({
                "permission": "deny",
                "agent_message": verdict.reason,
                "user_message": f"Blocked by {verdict.rule}",
            }, code=2)
        _emit_and_exit({"permission": "allow"})
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 -- see ON FAILING OPEN above
        _fail_open(exc, "cursor")
