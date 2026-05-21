import time
import threading
import json
import psutil
import webbrowser
import multiprocessing
from http.server import BaseHTTPRequestHandler, HTTPServer
from codecarbon import EmissionsTracker

# Global state to share between the background tasks and the web server
shared_state = {
    "phase": "Starting...",
    "cpu": 0,
    "power_watts": 0,
    "running": True,
    # Arrays to store instantaneous power readings so we can manually compute the perfect average
    "idle_power_readings": [],
    "cpu_power_readings": []
}

HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Live Energy Monitor</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/chartjs-plugin-annotation/2.2.1/chartjs-plugin-annotation.min.js"></script>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; text-align: center; background: #f4f4f9; margin: 0; padding: 20px; }
        .container { max-width: 900px; margin: auto; background: white; padding: 30px; border-radius: 12px; box-shadow: 0 8px 16px rgba(0,0,0,0.1); }
        h1 { color: #2c3e50; font-size: 2em; margin-bottom: 5px; }
        #phase { font-size: 1.4em; font-weight: bold; color: #e74c3c; margin-bottom: 25px; padding: 10px; background: #fdf2f2; border-radius: 8px; display: inline-block; }
        canvas { max-width: 100%; margin-top: 10px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Live Resource & Energy Monitor</h1>
        <div id="phase">Current Phase: Starting...</div>
        <canvas id="myChart" height="120"></canvas>
    </div>
    <script>
        const ctx = document.getElementById('myChart').getContext('2d');
        const chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [
                    { label: 'CPU Usage (%)', borderColor: '#e74c3c', backgroundColor: 'rgba(231, 76, 60, 0.1)', data: [], yAxisID: 'y', fill: true, tension: 0.3, pointRadius: 0 },
                    { label: 'Current Power (Watts)', borderColor: '#2ecc71', backgroundColor: 'rgba(46, 204, 113, 0.1)', data: [], yAxisID: 'y1', fill: true, tension: 0.3, pointRadius: 0 }
                ]
            },
            options: {
                animation: false, 
                interaction: { mode: 'index', intersect: false },
                plugins: { 
                    tooltip: { enabled: true },
                    annotation: {
                        annotations: {
                            line1: {
                                type: 'line',
                                scaleID: 'x',
                                value: '30.0', 
                                borderColor: 'orange',
                                borderWidth: 3,
                                borderDash: [5, 5],
                                label: {
                                    content: 'CPU Load Starts',
                                    display: true,
                                    position: 'start',
                                    backgroundColor: 'rgba(255, 165, 0, 0.9)'
                                }
                            }
                        }
                    }
                },
                scales: {
                    x: { title: { display: true, text: 'Time (seconds)', font: {weight: 'bold'} } },
                    y: { type: 'linear', position: 'left', min: 0, max: 100, title: { display: true, text: 'Resource Usage (%)', font: {weight: 'bold'} } },
                    y1: { type: 'linear', position: 'right', min: 0, title: { display: true, text: 'Current Power (Watts)', font: {weight: 'bold'} }, grid: { drawOnChartArea: false } }
                }
            }
        });

        let timeSeconds = 0;

        async function fetchData() {
            try {
                const response = await fetch('/data');
                const data = await response.json();
                
                document.getElementById('phase').innerText = "Current Phase: " + data.phase;
                
                if (!data.running) {
                    document.getElementById('phase').innerText = "Finished! Check your IDE console for final results.";
                    return; 
                }

                timeSeconds += 0.5;
                chart.data.labels.push(timeSeconds.toFixed(1));
                chart.data.datasets[0].data.push(data.cpu);
                chart.data.datasets[1].data.push(data.power_watts);

                if (chart.data.labels.length > 180) {
                    chart.data.labels.shift();
                    chart.data.datasets.forEach(ds => ds.data.shift());
                }

                chart.update();
                setTimeout(fetchData, 500);
            } catch (err) {
                console.error("Connection lost:", err);
                document.getElementById('phase').innerText = "Finished or Disconnected.";
            }
        }
        
        fetchData();
    </script>
</body>
</html>
"""

class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode('utf-8'))
        elif self.path == "/data":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(shared_state).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()
            
    def log_message(self, format, *args):
        pass 

def cpu_burner(end_time):
    """Spins indefinitely doing real math to force Apple P-cores to engage."""
    x = 0.0001
    while time.time() < end_time:
        x *= 1.000001
        x /= 0.999999
        x += 0.000001

def heavy_computation_all_cores(duration=40):
    shared_state["phase"] = "Heavy CPU Load"
    print(f"\n--- Phase: {shared_state['phase']} ---")
    end_time = time.time() + duration
    processes = []
    
    num_cores = multiprocessing.cpu_count()
    print(f"Spawning {num_cores} background processes to maximize CPU...")
    
    for _ in range(num_cores):
        p = multiprocessing.Process(target=cpu_burner, args=(end_time,))
        p.start()
        processes.append(p)
        
    for p in processes:
        p.join()

def run_workloads(tracker, server):
    # 0. WARMUP (10s)
    # Give the browser time to launch, render chart.js, and settle down.
    shared_state["phase"] = "Warming up (Ignoring Browser Launch)..."
    time.sleep(10)
    
    # 1. IDLE (20s)
    shared_state["phase"] = "Idle (Baseline)"
    print(f"\n--- Phase: {shared_state['phase']} ---")
    print("Measuring baseline energy for 20 seconds...")
    time.sleep(20)
    
    # 2. CPU LOAD (40s)
    print("Starting 40 seconds of maximum CPU load...")
    heavy_computation_all_cores(40)
    
    shared_state["phase"] = "Finished"
    shared_state["running"] = False
    print("\nWorkloads complete! Shutting down local web server...")
    time.sleep(2) 
    server.shutdown() 

def monitor_resources(tracker):
    """Polls the sensors every 0.5s and logs the exact wattage to calculate a perfect average."""
    while shared_state["running"]:
        shared_state["cpu"] = psutil.cpu_percent()
        try:
            power_w = sum(h.total_power().W for h in tracker._hardware)
            shared_state["power_watts"] = power_w
            
            # Store the instantaneous readings so we can average what was actually plotted!
            phase = shared_state["phase"]
            if phase == "Idle (Baseline)":
                shared_state["idle_power_readings"].append(power_w)
            elif phase == "Heavy CPU Load":
                shared_state["cpu_power_readings"].append(power_w)
                
        except Exception:
            shared_state["power_watts"] = 0
            
        time.sleep(0.5)

def main():
    print("Initializing CodeCarbon Energy Sensors...")
    tracker = EmissionsTracker(project_name="web_tutorial_demo", measure_power_secs=1)
    tracker.start()
    
    server = HTTPServer(('localhost', 8000), RequestHandler)
    
    workload_thread = threading.Thread(target=run_workloads, args=(tracker, server))
    monitor_thread = threading.Thread(target=monitor_resources, args=(tracker,))
    
    monitor_thread.start()
    workload_thread.start()
    
    print("\nStarting local server at http://localhost:8000")
    print("Opening your web browser automatically...")
    webbrowser.open("http://localhost:8000")
    
    server.serve_forever()
    
    workload_thread.join()
    monitor_thread.join()
    
    tracker.stop()
    print("\nCalculating summary from visual plot data...")
    
    idle_list = shared_state["idle_power_readings"]
    cpu_list = shared_state["cpu_power_readings"]
    total_list = idle_list + cpu_list
    
    avg_idle_watts = sum(idle_list) / len(idle_list) if idle_list else 0
    avg_cpu_watts = sum(cpu_list) / len(cpu_list) if cpu_list else 0
    avg_total_watts = sum(total_list) / len(total_list) if total_list else 0
    
    print("\n" + "="*55)
    print("               FINAL ENERGY EVALUATION")
    print("="*55)
    print(f"1. Average Power during 20s IDLE:      {avg_idle_watts:.2f} W")
    print(f"2. Average Power during 40s CPU LOAD:  {avg_cpu_watts:.2f} W")
    print("-" * 55)
    print(f"TOTAL Average Power (60s):             {avg_total_watts:.2f} W")
    print("="*55)

if __name__ == "__main__":
    main()
