param(
    [string]$ApiUrl = "http://127.0.0.1:8000/api/v1",
    [string]$Username = "analyst",
    [string]$Password = "ChangeMe-Analyst-2026!"
)

$ErrorActionPreference = "Stop"
$health = Invoke-RestMethod -Uri "$ApiUrl/health"
if ($health.status -ne "ok") { throw "API is not ready." }
$login = Invoke-RestMethod -Uri "$ApiUrl/auth/login" -Method Post -ContentType "application/json" -Body (@{ username = $Username; password = $Password } | ConvertTo-Json)
$headers = @{ Authorization = "Bearer $($login.access_token)" }
$graph = Invoke-RestMethod -Uri "$ApiUrl/graph?center_id=ENT-DEMO-P1001&depth=2" -Headers $headers
$analysis = Invoke-RestMethod -Uri "$ApiUrl/analytics/network?algorithm=centrality&center_id=ENT-DEMO-P1001" -Method Post -Headers $headers
$assistant = Invoke-RestMethod -Uri "$ApiUrl/assistant/query" -Method Post -Headers $headers -ContentType "application/json" -Body (@{ question = "What evidence supports Aarav Mehta?" } | ConvertTo-Json)
$report = Invoke-RestMethod -Uri "$ApiUrl/reports/synthesize" -Method Post -Headers $headers -ContentType "application/json" -Body (@{ case_id = "CASE-DEMO-2026-001"; title = "Windows demo synthesis" } | ConvertTo-Json)
[PSCustomObject]@{
    Health = $health.status
    GraphNodes = $graph.nodes.Count
    GraphEdges = $graph.edges.Count
    AnalysisMetrics = $analysis.metrics.Count
    AssistantGrounded = $assistant.grounded
    ReportId = $report.id
} | Format-List
