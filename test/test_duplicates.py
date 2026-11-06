from arsnel.organizer.duplicates import find_duplicates, hash_file


def test_hash_matches_known_sha256(tmp_path):
    target = tmp_path / "abc.txt"
    target.write_bytes(b"abc")
    assert hash_file(target) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_hash_is_chunk_size_independent(tmp_path):
    target = tmp_path / "big.bin"
    target.write_bytes(b"0123456789" * 1000)
    assert hash_file(target, chunk_size=7) == hash_file(target)


def test_finds_identical_files_across_folders(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    (tmp_path / "a" / "one.txt").write_bytes(b"same content")
    (tmp_path / "b" / "two.txt").write_bytes(b"same content")
    (tmp_path / "unique.txt").write_bytes(b"different!!!")
    groups = find_duplicates(tmp_path)
    assert len(groups) == 1
    assert {p.name for p in groups[0].paths} == {"one.txt", "two.txt"}
    assert groups[0].size == len(b"same content")


def test_same_size_different_content_is_not_flagged(tmp_path):
    (tmp_path / "a.bin").write_bytes(b"aaaa")
    (tmp_path / "b.bin").write_bytes(b"bbbb")
    assert find_duplicates(tmp_path) == []


def test_three_copies_form_one_group_and_wasted_bytes(tmp_path):
    for name in ("x", "y", "z"):
        (tmp_path / name).write_bytes(b"12345")
    (group,) = find_duplicates(tmp_path)
    assert len(group.paths) == 3
    assert group.wasted_bytes == 10


def test_groups_sorted_by_reclaimable_space(tmp_path):
    for name in ("s1", "s2"):
        (tmp_path / name).write_bytes(b"ab")
    for name in ("l1", "l2"):
        (tmp_path / name).write_bytes(b"a" * 100)
    groups = find_duplicates(tmp_path)
    assert [g.size for g in groups] == [100, 2]


def test_empty_files_ignored_unless_min_size_zero(tmp_path):
    (tmp_path / "e1").write_bytes(b"")
    (tmp_path / "e2").write_bytes(b"")
    assert find_duplicates(tmp_path) == []
    assert len(find_duplicates(tmp_path, min_size=0)) == 1


def test_hidden_folders_and_subfolders_respected(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "copy.txt").write_bytes(b"dup")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "copy.txt").write_bytes(b"dup")
    (tmp_path / "top.txt").write_bytes(b"dup")
    (group,) = find_duplicates(tmp_path)
    assert {p.name for p in group.paths} == {"copy.txt", "top.txt"}
    assert find_duplicates(tmp_path, recursive=False) == []


def test_progress_callback_reports_every_hashed_file(tmp_path):
    for name in ("a", "b", "c"):
        (tmp_path / name).write_bytes(b"same")
    calls = []
    find_duplicates(tmp_path, progress=lambda done, total: calls.append((done, total)))
    assert calls == [(1, 3), (2, 3), (3, 3)]
