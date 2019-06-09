#!/usr/bin/env python3

from collections import deque
from time import sleep
import urllib3.exceptions
from typing import Dict, Iterable, Optional
import argparse
import asyncio
import datetime
import math
import requests
import sys
import os
import json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument('url', metavar='URL', type=str)
    parser.add_argument('--request-history', metavar='N', type=int, default=10)
    parser.add_argument('--timeout', metavar='SEC', type=float, default=10.)

    return parser.parse_args()


def are_args_valid(args: argparse.Namespace) -> bool:
    return True


class Result(object):
    def __init__(
        self,
        *,
        response: Optional[requests.models.Response] = None,
        error: Optional[Exception] = None,
    ):
        self.response = response
        self.error = error

        if self.response is None or self.error is not None:
            self.is_success = False
        else:
            self.is_success = self.response.status_code >= 200 and self.response.status_code < 400


async def request(*, url: str, timeout: int) -> Result:
    try:
        response = requests.get(url, timeout=timeout)
        return Result(response=response)
    except Exception as e:
        return Result(response=None, error=e)


async def build_stats(results: Iterable[Result]) -> dict:
    no_results = len(results)
    no_successful_results = 0
    reason_counts: Dict[str, int] = {}
    sum_latency = 0

    for result in results:
        if result.is_success:
            no_successful_results += 1

        if result.response is not None:
            sum_latency += result.response.elapsed / datetime.timedelta(milliseconds=1)

        if result.error is not None:
            reason = str(type(result.error).__name__)
        else:
            reason = f"HTTP {result.response.status_code}"
        reason_counts[reason] = reason_counts.get(reason, 0) + 1

    success_rate = no_successful_results / no_results * 100.
    avg_latency = math.ceil(sum_latency / no_results)

    summary = {
        "Sample Size": no_results,
        "Success Rate": f"{success_rate:3.9f}%",
        "Average Latency": f"{avg_latency}ms",
        "Count by Reason": reason_counts,
    }

    return summary


async def render_stats(stats: dict, _format: str) -> None:
    if _format == "json":
        output = json.dumps(stats, indent=2)

    os.system('clear')
    print(output)


async def main()-> None:
    args = parse_args()
    assert are_args_valid(args)
    results = deque(maxlen=args.request_history)
    try:
        while True:
            result = await request(url=args.url, timeout=args.timeout)
            results.append(result)
            stats = await build_stats(results)
            await render_stats(stats, _format="json")
    except KeyboardInterrupt:
        os.system('clear')
        sys.exit(0)

if __name__ == "__main__":
    asyncio.run(main())