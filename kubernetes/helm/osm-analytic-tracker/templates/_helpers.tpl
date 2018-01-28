{{/*
Expand the name of the chart.
*/}}
{{- define "osmtracker.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Create a default fully qualified app name.
We truncate at 24 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
*/}}
{{- define "osmtracker.fullname" -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Common osmtracker arguments - common for multiple components.
*/}}
{{- define "osmtracker.common_args" -}}
"--db", "mongodb://$(DBUSER):$(DBPASSWD)@{{ .Values.db.service.name }}/{{ .Values.db.mongodbDatabase }}",
"--configdir", "/osmtracker-config",
"--amqp", "{{ .Values.amqp.service.name }}",
{{- if .Values.osmtracker.metrics.enabled }}
"--metrics",
{{- end }}
{{- if .Values.osmtracker.debug }}
"-lDEBUG",
{{- end }}
{{- end -}}
