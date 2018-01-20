{{/*
Expand the name of the chart.
*/}}
{{- define "name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 24 | trimSuffix "-" -}}
{{- end -}}

{{/*
Create a default fully qualified app name.
We truncate at 24 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
*/}}
{{- define "fullname" -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- printf "%s-%s" .Release.Name $name | trunc 24 | trimSuffix "-" -}}
{{- end -}}

{{/*
Common osmtracker arguments - common for multiple components.
*/}}
{{- define "osmtracker.common_args" -}}
"--db", "mongodb://$(DBUSER):$(DBPASSWD)@{{ .Values.db.service.name }}/{{ .Values.db.mongodbDatabase }}",
"--configdir", "/osmtracker-config",
{{- if .Values.amqp.enabled }}
"--amqp", "{{ .Values.amqp.service.name }}",
{{- end }}
{{- if .Values.osmtracker.debug }}
"-lDEBUG",
{{- end }}
{{- end -}}
