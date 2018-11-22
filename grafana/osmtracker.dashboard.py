from grafanalib.core import *

datasource = 'prometheus'

replication_lag_stat = SingleStat(
    title="Replication Lag",
    dataSource=datasource,
    targets=[
        Target(
            expr='time()-osmtracker_minutely_diff_timestamp',
            refId='A',
        ),
    ],
    format = SECONDS_FORMAT,
    valueMaps = VTYPE_AVG,
    valueFontSize = '100%',
    thresholds = '3:4',
    colorValue = True,
    sparkline = SparkLine(show=True),
    span = 3,
)

replication_seqno_rate_stat = SingleStat(
    title="OpenStreetMap Replication SeqNo Rate",
    dataSource=datasource,
    targets=[
        Target(
            expr='irate(osmtracker_minutely_diff_latest_seqno[10m])*60',
            refId='A',
        ),
    ],
    format = NO_FORMAT,
    valueMaps = VTYPE_AVG,
    valueFontSize = '100%',
    thresholds = '0.9,1.1',
    colors = [ORANGE, GREEN, ORANGE],
    colorValue = True,
    sparkline = SparkLine(show=True),
    span = 3,
)

minutely_diff_chgset_rate_stat = SingleStat(
    title="Minutely Diff Changeset Rate",
    dataSource=datasource,
    targets=[
        Target(
            expr='rate(osmtracker_minutely_diff_csets_observed[5m])*60',
            refId='A',
        ),
    ],
    format = NO_FORMAT,
    valueMaps = VTYPE_CURR,
    valueFontSize = '100%',
    thresholds = '0',
    colors = [GREEN, GREEN, RED],
    colorValue = True,
    sparkline = SparkLine(show=True),
    span = 3,
)

db_chgset_rate_stat = SingleStat(
    title="Database Changeset Rate",
    dataSource=datasource,
    targets=[
        Target(
            expr='sum(rate(osmtracker_changeset_cnt{state="DONE"}[1h]))*60',
            refId='A',
        ),
    ],
    format = NO_FORMAT,
    valueMaps = VTYPE_AVG,
    valueFontSize = '100%',
    thresholds = '0 0',
    colorValue = True,
    sparkline = SparkLine(show=True),
    span = 3,
)


replication_lag = Graph(
    title="OpenStreetMap Replication Lag",
    dataSource=datasource,
    targets=[
        Target(
            expr='time()-osmtracker_minutely_diff_processing_timestamp',
            legendFormat='Difftracker service lag',
            refId='A',
        ),
        Target(
            expr='time()-osmtracker_minutely_diff_timestamp',
            legendFormat='Total database lag',
            refId='B',
        ),
    ],
    yAxes=single_y_axis(format=SECONDS_FORMAT),
)

replication_seqno = Graph(
    title="Replication Sequence Number",
    dataSource=datasource,
    targets=[
        Target(
            expr='osmtracker_minutely_diff_head_seqno',
            legendFormat='Head SeqNo',
            refId='A',
        ),
        Target(
            expr='osmtracker_minutely_diff_latest_seqno',
            legendFormat='Latest Processed SeqNo',
            refId='B',
        ),
    ],
    yAxes=single_y_axis(format=SHORT_FORMAT, min=None, max=None),
)

chgsets_in_minutely_diff = Graph(
    title="Changesets in minutely diffs",
    dataSource=datasource,
    targets=[
        Target(
            expr='osmtracker_minutely_diff_csets_observed',
            legendFormat='Changesets per minutely diff',
            refId='A',
        ),
    ],
    yAxes=single_y_axis(format=SHORT_FORMAT),
)

chgsets_in_db = Graph(
    title="Changesets in database",
    dataSource=datasource,
    targets=[
        Target(
            expr='osmtracker_changeset_cnt',
            legendFormat='{{state}}',
            refId='A',
        ),
    ],
    yAxes=single_y_axis(format=SHORT_FORMAT),
    legend=Legend(rightSide=True),
)

event_rates = Graph(
    title="Event Rates",
    dataSource=datasource,
    targets=[
        Target(
            expr='sum(rate(osmtracker_events[5m])) by (event,action)',
            legendFormat='{{event}} - {{action}}',
            refId='A',
        ),
    ],
    yAxes=single_y_axis(format=SHORT_FORMAT),
    legend=Legend(rightSide=True),
)

events_table = Table(
    title="Events",
    dataSource=datasource,
    targets=[
        Target(
            expr='sum(osmtracker_events) by (event,action)',
            legendFormat='{{event}} - {{action}}',
            format = TABLE_TARGET_FORMAT,
            instant = True,
            refId='A',
        ),
    ],
    fontSize = '90%',
    scroll = True,
    sort = ColumnSort(col=2, desc=False),
    span = 3,
    styles = [ColumnStyle(alias="Event Type",
                          pattern="event",
                          type=NumberColumnStyleType()),
              ColumnStyle(alias="Direction",
                          pattern="action",
                          type=NumberColumnStyleType()),
              ColumnStyle(alias="Value",
                          pattern='Value',
                          type=NumberColumnStyleType(decimals=0)),
              ColumnStyle(pattern="Time",
                          type=HiddenColumnStyleType()),
              ColumnStyle(pattern="/.*/",),
    ],
    transform = TABLE_TRANSFORM,
)

component_memory_usage = Graph(
    title="Component Memory Usage",
    dataSource=datasource,
    targets=[
        Target(
            expr='label_replace(process_virtual_memory_bytes{app="osm-analytic-tracker"}, "instance", "$1", "instance", "(.*):.*")',
            legendFormat='{{instance}}',
            refId='A',
        ),
    ],
    yAxes=single_y_axis(format=BYTES_FORMAT, min=None, max=None),
    legend=Legend(rightSide=True),
)

component_cpu_usage = Graph(
    title="Component CPU Usage",
    dataSource=datasource,
    targets=[
        Target(
            expr='label_replace(process_cpu_seconds_total{app="osm-analytic-tracker"}, "instance", "$1", "instance", "(.*):.*")',
            legendFormat='{{instance}}',
            refId='A',
        ),
    ],
    yAxes=single_y_axis(format=SECONDS_FORMAT),
    legend=Legend(rightSide=True),
)

chgset_filtering_time = Graph(
    title="Changeset Filtering Processing Time",
    dataSource=datasource,
    targets=[
        Target(
            expr='histogram_quantile(0.95, rate(osmtracker_changeset_filter_processing_time_seconds_bucket[10m]))',
            legendFormat='.95 quantile',
            refId='A',
        ),
        Target(
            expr='histogram_quantile(0.90, rate(osmtracker_changeset_filter_processing_time_seconds_bucket[10m]))',
            legendFormat='.90 quantile',
            refId='B',
        ),
        Target(
            expr='histogram_quantile(0.80, rate(osmtracker_changeset_filter_processing_time_seconds_bucket[10m]))',
            legendFormat='.80 quantile',
            refId='C',
        ),
    ],
    yAxes=single_y_axis(format=SECONDS_FORMAT),
)

chgset_refresh_processing_time = Graph(
    title="Changeset Refresh Processing Time",
    dataSource=datasource,
    targets=[
        Target(
            expr='histogram_quantile(0.95, rate(osmtracker_changeset_refresh_processing_time_seconds_bucket[10m]))',
            legendFormat='.95 quantile',
            refId='A',
        ),
        Target(
            expr='histogram_quantile(0.90, rate(osmtracker_changeset_refresh_processing_time_seconds_bucket[10m]))',
            legendFormat='.90 quantile',
            refId='B',
        ),
        Target(
            expr='histogram_quantile(0.80, rate(osmtracker_changeset_refresh_processing_time_seconds_bucket[10m]))',
            legendFormat='.80 quantile',
            refId='C',
        ),
    ],
    yAxes=single_y_axis(format=SECONDS_FORMAT),
)

chgset_analysis_processing_time = Graph(
    title="Changeset Analysis Processing Time",
    dataSource=datasource,
    targets=[
        Target(
            expr='histogram_quantile(0.95, rate(osmtracker_changeset_analysis_processing_time_seconds_bucket[10m]))',
            legendFormat='.95 quantile',
            refId='A',
        ),
        Target(
            expr='histogram_quantile(0.90, rate(osmtracker_changeset_analysis_processing_time_seconds_bucket[10m]))',
            legendFormat='.90 quantile',
            refId='B',
        ),
        Target(
            expr='histogram_quantile(0.80, rate(osmtracker_changeset_analysis_processing_time_seconds_bucket[10m]))',
            legendFormat='.80 quantile',
            refId='C',
        ),
    ],
    yAxes=single_y_axis(format=SECONDS_FORMAT),
)

chgset_backend_refresh_processing_time = Graph(
    title="Changeset Backend Refresh Processing Time",
    dataSource=datasource,
    targets=[
        Target(
            expr='histogram_quantile(0.95, rate(osmtracker_backend_processing_time_seconds_bucket[10m]))',
            legendFormat='.95 quantile',
            refId='A',
        ),
        Target(
            expr='histogram_quantile(0.90, rate(osmtracker_backend_processing_time_seconds_bucket[10m]))',
            legendFormat='.90 quantile',
            refId='B',
        ),
        Target(
            expr='histogram_quantile(0.80, rate(osmtracker_backend_processing_time_seconds_bucket[10m]))',
            legendFormat='.80 quantile',
            refId='C',
        ),
    ],
    yAxes=single_y_axis(format=SECONDS_FORMAT),
)

osmapi_event_rates = Graph(
    title="OpenStreetMap API Event Rates [/hour]",
    dataSource=datasource,
    targets=[
        Target(
            expr='rate(openstreetmap_api_events[24h])*3600',
            legendFormat='{{operation}}',
            refId='A',
        ),
    ],
    yAxes=single_y_axis(format=SHORT_FORMAT),
    legend=Legend(rightSide=True),
)

osmapi_bytes_rates = Graph(
    title="OpenStreetMap API Bytes Rates [/hour]",
    dataSource=datasource,
    targets=[
        Target(
            expr='rate(openstreetmap_api_bytes[24h])*3600',
            legendFormat='{{operation}} - {{direction}}',
            refId='A',
        ),
    ],
    yAxes=single_y_axis(format=SHORT_FORMAT),
    legend=Legend(rightSide=True),
)

dashboard = Dashboard(
  title="OpenStreetMap Analytic Tracker Stats",
  rows=[
      Row(panels=[
          replication_lag_stat, replication_seqno_rate_stat, minutely_diff_chgset_rate_stat, db_chgset_rate_stat,
      ]),
      Row(panels=[
          replication_lag, replication_seqno, chgsets_in_minutely_diff, chgsets_in_db,
      ]),
      Row(panels=[
          event_rates, events_table, component_memory_usage, component_cpu_usage,
      ]),
      Row(panels=[
          chgset_filtering_time, chgset_refresh_processing_time, chgset_analysis_processing_time, chgset_backend_refresh_processing_time,
      ]),
      Row(panels=[
          osmapi_event_rates, osmapi_bytes_rates
      ]),
  ],
).auto_panel_ids()
