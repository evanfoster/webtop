#!/usr/bin/env python3

from threading import Event
from webtop import api
from yarl import URL
import argparse
import asyncio
import json
import os
import signal
import yaml


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument("url", metavar="URL", type=URL)

    parser.add_argument(
        "--method",
        metavar="VERB",
        help="HTTP method",
        type=str.upper,
        choices=["GET", "HEAD", "OPTIONS", "TRACE"],
        default="GET",
    )

    parser.add_argument("-k", "--workers", metavar="N", type=int, help="Number of workers", default=1)

    parser.add_argument(
        "--request-history", metavar="N", type=int, help="Number of request results to track", default=1000
    )

    parser.add_argument("--timeout", metavar="SEC", type=float, help="Request timeout threshold", default=1.0)

    parser.add_argument(
        "-o",
        "--output-format",
        metavar="FORMAT",
        type=str,
        choices=("json", "yaml"),
        help="Output format",
        default="json",
    )

    parser.add_argument("--resolve", metavar="HOST:ADDRESS", type=str, help="Manually resolve host to address")

    return parser.parse_args()


def _are_args_valid(args: argparse.Namespace) -> bool:
    return all(
        (
            args.url.is_absolute(),
            args.request_history >= 1,
            args.timeout > 0,
            args.workers > 0,
            args.resolve is None or ":" in args.resolve,
        )
    )


def _build_stats(statistics: api.Statistics) -> dict:
    return {
        "URL": statistics.url,
        "Verb": statistics.method,
        "Sample Size": statistics.sample_size,
        "Success Rate": f"{statistics.success_rate:3.9f}%",
        "Average Latency": f"{statistics.mean_latency}ms",
        "Count by Reason": statistics.reason_counts,
    }


def _render_stats(statistics: dict, *, _format: str) -> str:
    if _format == "json":
        output = json.dumps(statistics, indent=2)
    elif _format == "yaml":
        output = yaml.dump(statistics, default_flow_style=False, sort_keys=False)  # type: ignore
    return output


def _print_stats(statistics: api.Statistics, _format: str) -> None:
    stats = _build_stats(statistics)
    output = _render_stats(stats, _format=_format)
    os.system("clear")
    print(output, flush=True)


async def main() -> None:
    args = _parse_args()
    assert _are_args_valid(args)

    custom_resolution = {}
    if args.resolve is not None:
        host, address = args.resolve.split(":")
        if args.url.host == host:
            custom_resolution[host] = address

    runner = api.Runner(
        url=str(args.url),
        name_resolution_overrides=custom_resolution,
        method=args.method,
        number_of_running_requests=args.request_history,
        number_of_workers=args.workers,
        timeout=args.timeout
    )

    # asyncio.ensure_future will schedule the coroutine with the event loop, but won't block progress through your
    # function. It's basically asynchronous asynchronicity, as opposed to the synchronous asynchronicity you get with
    # await.
    running = asyncio.ensure_future(runner.start())

    shutdown_event = Event()

    # Signal handlers cannot be coroutines, because signal.signal doesn't know how to call a coroutine. This must be a
    # synchronous function. You can use asyncio.ensure_future to schedule runner.stop even though you're not in a
    # coroutine yourself.
    def shutdown_signal_handler(_, __):
        asyncio.ensure_future(runner.stop())
        shutdown_event.set()

    for shutdown_signal in (signal.SIGINT, signal.SIGTERM):
        signal.signal(shutdown_signal, shutdown_signal_handler)

    while not shutdown_event.is_set():
        _print_stats(runner.get_statistics(), _format=args.output_format)
        # time.sleep blocks the event loop. Anything that could block the event loop **MUST** be either asynchronous, or
        # wrapped in a thread. If it blocks your function from moving forward and there's not an await in front of it,
        # then your program will hang forever.
        await asyncio.sleep(0.1)
    await running


if __name__ == "__main__":
    asyncio.run(main())
