import asyncio

from app.runtime.ack_tracker import OffsetCommitTracker


def test_ack_tracker_commits_only_contiguous_offsets() -> None:
    async def scenario() -> None:
        tracker = OffsetCommitTracker(initial_offset=100)

        commit = await tracker.mark_processed(sequence_number=2, next_offset=103)
        assert commit is None

        commit = await tracker.mark_processed(sequence_number=1, next_offset=102)
        assert commit == 103

    asyncio.run(scenario())


def test_ack_tracker_skips_none_offsets_until_real_offset() -> None:
    async def scenario() -> None:
        tracker = OffsetCommitTracker(initial_offset=None)

        commit = await tracker.mark_processed(sequence_number=1, next_offset=None)
        assert commit is None

        commit = await tracker.mark_processed(sequence_number=2, next_offset=301)
        assert commit == 301

    asyncio.run(scenario())
