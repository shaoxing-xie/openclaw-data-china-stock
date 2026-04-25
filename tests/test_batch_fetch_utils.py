from plugins.data_collection.utils.batch_fetch import batch_fetch_parallel


def test_batch_fetch_parallel_collects_source_stats():
    def fetch(item: str):
        return {"success": True, "source_id": "mock", "data": {"item": item}}

    result = batch_fetch_parallel(["a", "b", "c"], fetch, max_workers=2, batch_size=2)

    assert result["success"] is True
    assert result["success_count"] == 3
    assert result["per_source_stats"]["mock"]["success"] == 3
    assert "total_ms" in result
    assert "queue_ms" in result


def test_batch_fetch_parallel_handles_failures():
    def fetch(item: str):
        if item == "bad":
            return {"success": False, "source_id": "mock", "message": "boom"}
        return {"success": True, "source_id": "mock", "data": {"item": item}}

    result = batch_fetch_parallel(["ok", "bad"], fetch, max_workers=2, batch_size=1)

    assert result["success"] is True
    assert result["failed_count"] == 1
    assert result["errors"]["bad"] == "boom"
    assert result["per_source_stats"]["mock"]["failed"] == 1
