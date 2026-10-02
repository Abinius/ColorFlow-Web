# Push a local commit via GitHub Git Data API (github.com:443 blocked fallback)
# Reuses remote blob SHAs for unchanged files; only uploads changed ones.
# Code is ASCII-only on purpose: Chinese Windows PowerShell reads .ps1 without
# BOM as GBK, which breaks Chinese string literals during parsing.
$ErrorActionPreference = "Stop"

$cred = "protocol=https`nhost=github.com`n" | & git credential fill 2>&1
$token = ($cred | Select-String "password=(.+)").Matches[0].Groups[1].Value.Trim()
if (-not $token) { throw "No token from credential manager" }
Write-Host "  token: $($token.Substring(0,10))... ($($token.Length) chars)"

$repo   = "Abinius/ColorFlow-Web"
$branch = "main"
$base   = "https://api.github.com/repos/$repo"
$h      = @{ Authorization = "Bearer $token"; Accept = "application/vnd.github+json" }

function Call([string]$method, [string]$url, [object]$obj) {
    # The JSON body MUST be sent as UTF-8 BYTES. Passing a .NET string to -Body
    # makes Windows PowerShell 5.1 encode it with the process ANSI codepage,
    # which replaces every non-ASCII character with '?' (and downgrades
    # full-width punctuation). That silently rewrites the commit message and
    # therefore produces a different commit SHA -- the exact failure this
    # script exists to avoid. Identical trap in the response direction: no
    # charset is negotiated for a string body, so keep this ASCII-only.
    $json = $null
    if ($null -ne $obj) { $json = $obj | ConvertTo-Json -Depth 40 }
    if ($null -eq $json) {
        return Invoke-RestMethod -Uri $url -Headers $h -Method $method
    }
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($json)
    Invoke-RestMethod -Uri $url -Headers $h -Method $method `
        -Body $bytes -ContentType "application/json; charset=utf-8"
}

Write-Host "`n=== 1. remote state ==="
$ref = Invoke-RestMethod -Uri "$base/git/ref/heads/$branch" -Headers $h -Method Get
$remoteHead = $ref.object.sha
Write-Host "  remote HEAD: $remoteHead"

$localParent = (git rev-parse "HEAD^")
if ($localParent -ne $remoteHead) {
    throw "local HEAD^ ($localParent) != remote HEAD ($remoteHead); sync first, aborting to protect data"
}
Write-Host "  parent match OK"

# /git/trees needs a TREE sha, not a commit sha
$remoteCommitObj = Invoke-RestMethod -Uri "$base/git/commits/$remoteHead" -Headers $h -Method Get
$remoteTreeSha = $remoteCommitObj.tree.sha
Write-Host "  remote tree: $remoteTreeSha"

Write-Host "`n=== 2. remote tree (recursive + paginated) ==="
function GetTree([string]$url) {
    $all = @()
    while ($url) {
        $r = Invoke-RestMethod -Uri $url -Headers $h -Method Get
        $all += $r.tree
        if ($r.next_page_url) { $url = $r.next_page_url } else { $url = $null }
    }
    return $all
}
$remoteMap = @{}
foreach ($t in (GetTree "$base/git/trees/${remoteTreeSha}?recursive=1")) {
    $remoteMap[$t.path] = [pscustomobject]@{ sha = $t.sha; mode = $t.mode; type = $t.type }
}
Write-Host "  remote entries: $($remoteMap.Count)"

Write-Host "`n=== 3. local tree + classify ==="
$treeOut = "$env:TEMP\cf_tree.txt"
# Use Start-Process -RedirectStandardOutput so raw bytes (NUL separators + UTF-8
# paths like docs/04-dev-plan.md) are written verbatim, unlike '>' which re-encodes.
$p1 = Start-Process -FilePath git -ArgumentList @("ls-tree","-r","-z","HEAD") `
        -NoNewWindow -Wait -PassThru -RedirectStandardOutput $treeOut
if ($p1.ExitCode -ne 0) { throw "git ls-tree failed (exit $($p1.ExitCode))" }
$raw = [System.IO.File]::ReadAllBytes($treeOut)
$text = [System.Text.Encoding]::UTF8.GetString($raw)
$files = @()
$i = 0
while ($i -lt $text.Length) {
    $n = $text.IndexOf("`0", $i)
    if ($n -lt 0) { $n = $text.Length }
    $entry = $text.Substring($i, $n - $i)
    $tab = $entry.IndexOf("`t")
    $files += [pscustomobject]@{ meta = $entry.Substring(0, $tab); path = $entry.Substring($tab + 1) }
    $i = $n + 1
}
Remove-Item $treeOut -Force
Write-Host "  local files : $($files.Count)"

# commit message: read raw bytes then UTF-8 decode (git emits UTF-8 regardless of console codepage)
$msgOut = "$env:TEMP\cf_msg.txt"
$p2 = Start-Process -FilePath git -ArgumentList @("log","-1","--format=%B") `
        -NoNewWindow -Wait -PassThru -RedirectStandardOutput $msgOut
if ($p2.ExitCode -ne 0) { throw "git log failed (exit $($p2.ExitCode))" }
$msg = [System.Text.Encoding]::UTF8.GetString([System.IO.File]::ReadAllBytes($msgOut))
Remove-Item $msgOut -Force

# author/committer identity: preserve the local commit's metadata so the API-built
# commit is byte-identical to the local one (same SHA). Fields are 0x1f-separated.
$metaOut = "$env:TEMP\cf_meta.txt"
$p2m = Start-Process -FilePath git -ArgumentList @("log","-1","--format=%an%x1f%ae%x1f%aI%x1f%cn%x1f%ce%x1f%cI") `
        -NoNewWindow -Wait -PassThru -RedirectStandardOutput $metaOut
if ($p2m.ExitCode -ne 0) { throw "git log meta failed (exit $($p2m.ExitCode))" }
$metaRaw = [System.Text.Encoding]::UTF8.GetString([System.IO.File]::ReadAllBytes($metaOut))
Remove-Item $metaOut -Force
$sep = [string][char]0x1F
$m = $metaRaw -split $sep
$authorName = $m[0]; $authorEmail = $m[1]; $authorDate = $m[2]
$committerName = $m[3]; $committerEmail = $m[4]; $committerDate = $m[5]

$modeToApi = @{ "100644" = "100644"; "100755" = "100755"; "120000" = "120000" }
$treeEntries = @()
$uploads = 0; $reuses = 0; $deletes = 0
foreach ($f in $files) {
    $parts = $f.meta -split " "
    $mode  = $parts[0]
    $locSha = $parts[2]
    if ($remoteMap.ContainsKey($f.path) -and $remoteMap[$f.path].sha -eq $locSha) {
        $reuses++
        continue
    }
    # read the blob from git's object store (LF-normalized) instead of the working
    # tree: with core.autocrlf=true the working tree has CRLF, which would create
    # blobs with different SHAs than what git actually stores
    $tmpOut = "$env:TEMP\cf_blob_$locSha.txt"
    $pb = Start-Process -FilePath git -ArgumentList @("cat-file","blob",$locSha) `
            -NoNewWindow -Wait -PassThru -RedirectStandardOutput $tmpOut
    if ($pb.ExitCode -ne 0) { throw "git cat-file failed for $($f.path) (exit $($pb.ExitCode))" }
    $rb = [System.IO.File]::ReadAllBytes($tmpOut)
    Remove-Item $tmpOut -Force
    $blob = Call "POST" "$base/git/blobs" ([pscustomobject]@{ content = [Convert]::ToBase64String($rb); encoding = "base64" })
    $treeEntries += [pscustomobject]@{ path = $f.path; mode = $modeToApi[$mode]; type = "blob"; sha = $blob.sha }
    Write-Host "  upload $($f.path) ($($rb.Length) B)"
    $uploads++
}
foreach ($p in $remoteMap.Keys) {
    # only delete remote blobs; never touch tree/dir entries (would drop whole dirs)
    if ($remoteMap[$p].type -ne "blob") { continue }
    if (-not (($files | ForEach-Object { $_.path }) -contains $p)) {
        $treeEntries += [pscustomobject]@{ path = $p; mode = "100644"; type = "blob"; sha = $null }
        Write-Host "  delete $p"
        $deletes++
    }
}
Write-Host "  summary: upload=$uploads  reuse=$reuses  delete=$deletes"

Write-Host "`n=== 4. create tree ==="
$newTree = Call "POST" "$base/git/trees" ([pscustomobject]@{
    base_tree = $remoteTreeSha; tree = $treeEntries
})
Write-Host "  tree: $($newTree.sha)"

Write-Host "`n=== 5. create commit ==="
$newCommit = Call "POST" "$base/git/commits" ([pscustomobject]@{
    message = $msg; tree = $newTree.sha; parents = @($remoteHead)
    author    = [pscustomobject]@{ name = $authorName; email = $authorEmail; date = $authorDate }
    committer = [pscustomobject]@{ name = $committerName; email = $committerEmail; date = $committerDate }
})
Write-Host "  commit: $($newCommit.sha)"

# Fail fast, before touching the ref. This route only exists to reproduce the
# local commit byte-for-byte, so the API-built commit MUST hash to the same SHA.
# A mismatch means the message, the dates (the original timezone offset must be
# preserved, e.g. +08:00 -- never normalise it to UTC) or the tree differ; moving
# the ref then would leave the two branches permanently diverged, and the parent
# check in step 1 would abort every future run.
$localHead = (git rev-parse HEAD).Trim()
if ($newCommit.sha -ne $localHead) {
    throw "API-built commit $($newCommit.sha) != local HEAD $localHead; refusing to update ref (would diverge)"
}
Write-Host "  matches local HEAD (byte-identical)"

Write-Host "`n=== 6. update ref (optimistic concurrency check) ==="
$ref2 = Invoke-RestMethod -Uri "$base/git/ref/heads/$branch" -Headers $h -Method Get
if ($ref2.object.sha -ne $remoteHead) {
    throw "remote advanced to $($ref2.object.sha) since start; aborting to protect data"
}
$upd = Call "PATCH" "$base/git/refs/heads/$branch" ([pscustomobject]@{
    sha = $newCommit.sha; force = $false
})
Write-Host "  ref: $($upd.ref) -> $($upd.object.sha)"

Write-Host "`n=== 7. verify ==="
$verify = Invoke-RestMethod -Uri "$base/git/commits/$($upd.object.sha)" -Headers $h -Method Get
$lines = $verify.message -split "`n"
Write-Host "  subject: $($lines[0])"
Write-Host "  tree   : $($verify.tree.sha)"
Write-Host "  parent : $($verify.parents[0].sha)"
Write-Host "`nDONE"
