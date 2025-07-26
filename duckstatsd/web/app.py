import argparse
from flask import Flask, render_template, request
import plotly.graph_objects as go
import plotly.express as px
from plotly.utils import PlotlyJSONEncoder
from datetime import datetime

from .database import MetricsDB


def create_app(db_path: str = "metrics.db"):
    app = Flask(__name__)
    app.json_encoder = PlotlyJSONEncoder

    db = MetricsDB(db_path)

    @app.route("/")
    def dashboard():
        """Dashboard with recent activity and summary."""
        time_range = int(request.args.get("hours", 24))

        recent_metrics = db.get_recent_metrics(50)
        metrics_summary = db.get_metrics_summary(time_range)
        active_metrics = db.get_active_metrics(1, 10)
        tag_summary = db.get_tag_summary(time_range)

        # Format timestamps for display
        for metric in recent_metrics:
            if metric["timestamp"]:
                dt = datetime.fromisoformat(metric["timestamp"])
                metric["timestamp_display"] = dt.strftime("%H:%M:%S")

        return render_template(
            "dashboard.html",
            recent_metrics=recent_metrics,
            metrics_summary=metrics_summary,
            active_metrics=active_metrics,
            tag_summary=tag_summary,
            time_range=time_range,
            current_page="dashboard",
        )

    @app.route("/counters")
    def counters():
        """Counters page with rate chart."""
        selected_counter = request.args.get("metric")
        selected_tag_key = request.args.get("tag_key")
        time_range = int(request.args.get("hours", 24))

        counter_metrics = db.get_counter_metrics()
        available_tag_keys = db.get_all_tag_keys()
        chart_html = None

        if selected_counter:
            if selected_tag_key:
                # Tag-grouped chart
                timeseries_data = db.get_counter_timeseries_by_tag(
                    selected_counter, selected_tag_key, time_range
                )

                if timeseries_data:
                    # Group by tag value
                    tag_groups = {}
                    for item in timeseries_data:
                        tag_value = item["tag_value"] or "null"
                        if tag_value not in tag_groups:
                            tag_groups[tag_value] = {"times": [], "counts": []}
                        tag_groups[tag_value]["times"].append(item["minute"])
                        tag_groups[tag_value]["counts"].append(item["count"])

                    fig = go.Figure()
                    for tag_value, data in tag_groups.items():
                        fig.add_trace(
                            go.Scatter(
                                x=data["times"],
                                y=data["counts"],
                                mode="lines+markers",
                                name=f"{selected_tag_key}={tag_value}",
                                line=dict(width=2),
                            )
                        )

                    fig.update_layout(
                        title=f"Counter Rate: {selected_counter} by {selected_tag_key}",
                        xaxis_title="Time",
                        yaxis_title="Events per Minute",
                        height=400,
                        margin=dict(l=0, r=0, t=40, b=0),
                    )

                    chart_html = fig.to_html(
                        include_plotlyjs="cdn", div_id="counter-chart"
                    )
            else:
                # Regular chart
                timeseries_data = db.get_counter_timeseries(
                    selected_counter, time_range
                )

                if timeseries_data:
                    times = [item["minute"] for item in timeseries_data]
                    counts = [item["count"] for item in timeseries_data]

                    fig = go.Figure()
                    fig.add_trace(
                        go.Scatter(
                            x=times,
                            y=counts,
                            mode="lines+markers",
                            name=selected_counter,
                            line=dict(width=2),
                        )
                    )

                    fig.update_layout(
                        title=f"Counter Rate: {selected_counter}",
                        xaxis_title="Time",
                        yaxis_title="Events per Minute",
                        height=400,
                        margin=dict(l=0, r=0, t=40, b=0),
                    )

                    chart_html = fig.to_html(
                        include_plotlyjs="cdn", div_id="counter-chart"
                    )

        return render_template(
            "counters.html",
            counter_metrics=counter_metrics,
            selected_counter=selected_counter,
            selected_tag_key=selected_tag_key,
            available_tag_keys=available_tag_keys,
            chart_html=chart_html,
            time_range=time_range,
            current_page="counters",
        )

    @app.route("/gauges")
    def gauges():
        """Gauges page with trend chart."""
        selected_gauge = request.args.get("metric")
        time_range = int(request.args.get("hours", 24))

        gauge_metrics = db.get_gauge_metrics()
        chart_html = None
        stats = None

        if selected_gauge:
            timeseries_data = db.get_gauge_timeseries(selected_gauge, time_range)

            if timeseries_data:
                times = [item["timestamp"] for item in timeseries_data]
                values = [item["value"] for item in timeseries_data]

                fig = go.Figure()
                fig.add_trace(
                    go.Scatter(
                        x=times,
                        y=values,
                        mode="lines+markers",
                        name=selected_gauge,
                        line=dict(width=2),
                    )
                )

                fig.update_layout(
                    title=f"Gauge Trend: {selected_gauge}",
                    xaxis_title="Time",
                    yaxis_title="Value",
                    height=400,
                    margin=dict(l=0, r=0, t=40, b=0),
                )

                chart_html = fig.to_html(include_plotlyjs="cdn", div_id="gauge-chart")

                # Calculate stats
                stats = {
                    "min": min(values),
                    "max": max(values),
                    "avg": sum(values) / len(values),
                }

        return render_template(
            "gauges.html",
            gauge_metrics=gauge_metrics,
            selected_gauge=selected_gauge,
            chart_html=chart_html,
            stats=stats,
            time_range=time_range,
            current_page="gauges",
        )

    @app.route("/timers")
    def timers():
        """Timers page with histogram."""
        selected_timer = request.args.get("metric")
        time_range = int(request.args.get("hours", 24))

        timer_metrics = db.get_timer_metrics()
        chart_html = None

        if selected_timer:
            timer_values = db.get_timer_values(selected_timer, time_range)

            if timer_values:
                fig = go.Figure()
                fig.add_trace(
                    go.Histogram(x=timer_values, name=selected_timer, nbinsx=20)
                )

                fig.update_layout(
                    title=f"Timer Distribution: {selected_timer}",
                    xaxis_title="Duration (ms)",
                    yaxis_title="Frequency",
                    height=400,
                    margin=dict(l=0, r=0, t=40, b=0),
                )

                chart_html = fig.to_html(include_plotlyjs="cdn", div_id="timer-chart")

        return render_template(
            "timers.html",
            timer_metrics=timer_metrics,
            selected_timer=selected_timer,
            chart_html=chart_html,
            time_range=time_range,
            current_page="timers",
        )

    @app.route("/sets")
    def sets():
        """Sets page with cardinality info."""
        selected_set = request.args.get("metric")

        set_metrics = db.get_set_metrics()
        recent_members = []

        if selected_set:
            recent_members = db.get_set_members(selected_set, 20)

        return render_template(
            "sets.html",
            set_metrics=set_metrics,
            selected_set=selected_set,
            recent_members=recent_members,
            current_page="sets",
        )

    @app.route("/tags")
    def tags():
        """Tags explorer page."""
        selected_tag_key = request.args.get("tag_key")

        tag_keys = db.get_all_tag_keys()
        tag_values = []
        tag_summary = db.get_tag_summary(24)
        top_combinations = db.get_top_tag_combinations(10)
        recent_tagged_metrics = db.get_recent_tagged_metrics(20)

        if selected_tag_key:
            tag_values = db.get_tag_values(selected_tag_key, 50)

        return render_template(
            "tags.html",
            tag_keys=tag_keys,
            selected_tag_key=selected_tag_key,
            tag_values=tag_values,
            tag_summary=tag_summary,
            top_combinations=top_combinations,
            recent_tagged_metrics=recent_tagged_metrics,
            current_page="tags",
        )

    @app.route("/raw")
    def raw_data():
        """Raw data page with filtering and pagination."""
        page = int(request.args.get("page", 1))
        limit = 100
        offset = (page - 1) * limit

        metric_name = request.args.get("metric_name", "").strip()
        metric_type = request.args.get("metric_type", "")
        tag_filter = request.args.get("tag_filter", "").strip()
        hours = request.args.get("hours", "")

        # Convert empty strings to None
        filters = {
            "metric_name": metric_name or None,
            "metric_type": metric_type or None,
            "tag_filter": tag_filter or None,
            "hours": int(hours) if hours else None,
        }

        raw_metrics = db.get_raw_metrics(limit, offset, **filters)

        # Format timestamps
        for metric in raw_metrics:
            if metric["timestamp"]:
                dt = datetime.fromisoformat(metric["timestamp"])
                metric["timestamp_display"] = dt.strftime("%Y-%m-%d %H:%M:%S")

        return render_template(
            "raw.html",
            raw_metrics=raw_metrics,
            page=page,
            has_next=len(raw_metrics) == limit,
            filters=request.args,
            current_page="raw",
        )

    return app


def main():
    parser = argparse.ArgumentParser(description="DuckStatsD Web UI")
    parser.add_argument("--db", default="metrics.db", help="SQLite database file")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=5000, help="Port to bind to")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")

    args = parser.parse_args()

    app = create_app(args.db)
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
