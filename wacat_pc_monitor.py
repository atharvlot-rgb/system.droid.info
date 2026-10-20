
import tkinter as tk
from tkinter import ttk, messagebox
import psutil
import platform
import socket
import subprocess
import threading
import os
import time
from datetime import datetime

# WACAT PC MONITOR - lightweight Windows edition
BG = "#f3f5f9"
WHITE = "#ffffff"
BLUE = "#2864dc"
DARK = "#182230"
GREY = "#667085"
GREEN = "#159467"


class WacatPCMonitor:
    def __init__(self, root):
        self.root = root
        self.root.title("Wacat PC Monitor")
        self.root.geometry("1050x700")
        self.root.minsize(780, 520)
        self.root.configure(bg=BG)
        self.running = True
        self.history = []

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", padding=(12, 9))
        style.configure("Treeview", rowheight=24)
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))
        style.configure("TProgressbar", thickness=10)

        header = tk.Frame(root, bg=WHITE, padx=20, pady=13)
        header.pack(fill="x")
        tk.Label(header, text="WACAT", font=("Segoe UI", 21, "bold"),
                 bg=WHITE, fg=BLUE).pack(side="left")
        tk.Label(header, text="PC MONITOR",
                 font=("Segoe UI", 11), bg=WHITE, fg=GREY).pack(
                     side="left", padx=14)
        self.clock = tk.Label(header, bg=WHITE, fg=GREY)
        self.clock.pack(side="right")

        self.status = tk.Label(root, text="Starting monitor...",
                               bg=BG, fg=GREY, anchor="w", padx=20)
        self.status.pack(fill="x", pady=7)

        self.tabs = ttk.Notebook(root)
        self.tabs.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self.dashboard = self.tab("Dashboard")
        self.health_tab = self.tab("PC Health")
        self.process_tab = self.tab("Processes")
        self.drive_tab = self.tab("Drives")
        self.system_tab = self.tab("System")
        self.network_tab = self.tab("Network & Tools")

        self.build_dashboard()
        self.build_health()
        self.build_processes()
        self.build_drives()
        self.build_system()
        self.build_network()

        # Prime CPU counters before periodic refresh.
        psutil.cpu_percent(interval=None)
        for p in psutil.process_iter():
            try:
                p.cpu_percent(None)
            except (psutil.Error, OSError):
                pass

        self.refresh()
        self.refresh_health()
        self.refresh_drives()
        self.refresh_system()
        self.update_clock()
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def tab(self, name):
        frame = ttk.Frame(self.tabs, padding=12)
        self.tabs.add(frame, text=name)
        return frame

    def heading(self, parent, title, subtitle=""):
        tk.Label(parent, text=title, font=("Segoe UI", 17, "bold"),
                 bg=BG, fg=DARK).pack(anchor="w", pady=(4, 2))
        if subtitle:
            tk.Label(parent, text=subtitle, font=("Segoe UI", 9),
                     bg=BG, fg=GREY).pack(anchor="w", pady=(0, 10))

    def button(self, parent, text, command):
        tk.Button(parent, text=text, command=command, bg=WHITE,
                  fg=BLUE, activebackground="#e8efff",
                  relief="solid", bd=1, padx=10, pady=6,
                  cursor="hand2").pack(side="left", padx=(0, 6), pady=4)

    def card(self, parent, title):
        frame = tk.Frame(parent, bg=WHITE, highlightbackground="#e1e6ef",
                         highlightthickness=1, padx=12, pady=10)
        tk.Label(frame, text=title, bg=WHITE, fg=GREY,
                 font=("Segoe UI", 10)).pack(anchor="w")
        value = tk.Label(frame, text="--", bg=WHITE, fg=DARK,
                         font=("Segoe UI", 23, "bold"))
        value.pack(anchor="w", pady=3)
        bar = ttk.Progressbar(frame, maximum=100)
        bar.pack(fill="x", pady=(5, 0))
        return frame, value, bar

    def build_dashboard(self):
        f = self.dashboard
        self.heading(f, "PC Dashboard", "Live system performance")

        cards = tk.Frame(f, bg=BG)
        cards.pack(fill="x", pady=5)
        self.metrics = {}

        for name in ("CPU", "RAM", "Disk"):
            frame, value, bar = self.card(cards, name + " Usage")
            frame.pack(side="left", fill="both", expand=True, padx=4)
            self.metrics[name] = (value, bar)

        graph_card = tk.Frame(f, bg=WHITE, padx=12, pady=10)
        graph_card.pack(fill="both", expand=True, pady=8)
        tk.Label(graph_card, text="Performance History",
                 font=("Segoe UI", 11, "bold"),
                 bg=WHITE, fg=DARK).pack(anchor="w")
        self.graph = tk.Canvas(graph_card, bg=WHITE, height=150,
                               highlightthickness=0)
        self.graph.pack(fill="both", expand=True)

        self.summary = tk.Label(f, text="", bg=BG, fg=DARK,
                                justify="left", anchor="w")
        self.summary.pack(fill="x", pady=5)

        actions = tk.Frame(f, bg=BG)
        actions.pack(fill="x")
        self.button(actions, "Task Manager",
                    lambda: self.open_tool("taskmgr"))
        self.button(actions, "Device Manager",
                    lambda: self.open_tool("devmgmt.msc"))
        self.button(actions, "Command Prompt",
                    lambda: self.open_tool("cmd"))

    def build_health(self):
        f = self.health_tab
        self.heading(f, "PC Health", "Basic software health checks")
        self.health_text = tk.Text(f, bg=WHITE, fg=DARK,
                                   font=("Consolas", 10), wrap="word",
                                   relief="flat", padx=12, pady=12)
        self.health_text.pack(fill="both", expand=True, pady=8)
        self.button(f, "Run Health Checks", self.refresh_health)

    def build_processes(self):
        f = self.process_tab
        self.heading(f, "Running Processes", "Sorted by memory use")
        controls = tk.Frame(f, bg=BG)
        controls.pack(fill="x")
        self.button(controls, "Refresh Processes", self.refresh_processes)
        self.button(controls, "Open Task Manager",
                    lambda: self.open_tool("taskmgr"))

        cols = ("pid", "name", "cpu", "ram", "status")
        self.proc_tree = ttk.Treeview(f, columns=cols, show="headings")
        for col, title, width in [
            ("pid", "PID", 75), ("name", "Process", 300),
            ("cpu", "CPU %", 90), ("ram", "RAM MB", 100),
            ("status", "Status", 110)
        ]:
            self.proc_tree.heading(col, text=title)
            self.proc_tree.column(col, width=width)
        self.proc_tree.pack(fill="both", expand=True, pady=8)

    def build_drives(self):
        f = self.drive_tab
        self.heading(f, "Storage & Drives", "Mounted disks")
        cols = ("drive", "total", "used", "free", "percent")
        self.drive_tree = ttk.Treeview(f, columns=cols, show="headings")
        for col, title, width in [
            ("drive", "Drive", 200), ("total", "Total GB", 110),
            ("used", "Used GB", 110), ("free", "Free GB", 110),
            ("percent", "Used %", 100)
        ]:
            self.drive_tree.heading(col, text=title)
            self.drive_tree.column(col, width=width)
        self.drive_tree.pack(fill="both", expand=True, pady=8)
        self.button(f, "Refresh Drives", self.refresh_drives)

    def build_system(self):
        f = self.system_tab
        self.heading(f, "System Information")
        self.system_text = tk.Text(f, bg=WHITE, fg=DARK,
                                   font=("Consolas", 10), wrap="word",
                                   relief="flat", padx=12, pady=12)
        self.system_text.pack(fill="both", expand=True, pady=8)
        self.button(f, "Refresh Information", self.refresh_system)

    def build_network(self):
        f = self.network_tab
        self.heading(f, "Network & Tools",
                     "Run network checks and manage Python packages")

        row = tk.Frame(f, bg=BG)
        row.pack(fill="x")
        self.button(row, "Test Internet", self.test_internet)
        self.button(row, "Check DNS", self.check_dns)
        self.button(row, "Show Wi-Fi", self.show_wifi)
        self.button(row, "Flush DNS", self.flush_dns)

        install = tk.Frame(f, bg=BG)
        install.pack(fill="x", pady=8)
        tk.Label(install, text="Python package:",
                 bg=BG, fg=DARK).pack(side="left")
        self.package = tk.Entry(install, width=22)
        self.package.pack(side="left", padx=8)
        self.package.insert(0, "requests")
        self.button(install, "Install", self.install_package)
        self.button(install, "Python / pip", self.python_check)

        self.net_output = tk.Text(f, bg=WHITE, fg=DARK,
                                  font=("Consolas", 9), wrap="word",
                                  relief="flat", padx=10, pady=10)
        self.net_output.pack(fill="both", expand=True, pady=5)
        self.write_output("Wacat Network Tools ready.\n")

    def open_tool(self, command):
        try:
            subprocess.Popen(command, shell=True)
        except Exception as e:
            messagebox.showerror("Wacat", str(e))

    def refresh(self):
        if not self.running:
            return
        try:
            cpu = psutil.cpu_percent(None)
            ram = psutil.virtual_memory()
            root_path = os.environ.get("SystemDrive", "C:") + "\\"
            disk = psutil.disk_usage(root_path)

            for name, amount in [
                ("CPU", cpu), ("RAM", ram.percent), ("Disk", disk.percent)
            ]:
                value, bar = self.metrics[name]
                value.config(text=f"{amount:.0f}%")
                bar["value"] = amount

            self.history.append((cpu, ram.percent))
            self.history = self.history[-60:]
            self.draw_graph()

            uptime = max(0, int(time.time() - psutil.boot_time()))
            self.summary.config(text=(
                f"Processor: {psutil.cpu_count(logical=False) or '?'} physical / "
                f"{psutil.cpu_count()} logical cores     "
                f"RAM: {ram.used / 2**30:.1f}/{ram.total / 2**30:.1f} GB\n"
                f"Available RAM: {ram.available / 2**30:.1f} GB     "
                f"System uptime: {uptime // 3600}h {(uptime % 3600) // 60}m\n"
                f"Free system drive space: {disk.free / 2**30:.1f} GB"
            ))
            self.status.config(text="Monitoring active • Refresh every 2 seconds")
        except Exception as e:
            self.status.config(text=f"Some stats unavailable: {e}")

        self.root.after(2000, self.refresh)

    def draw_graph(self):
        c = self.graph
        c.delete("all")
        w = max(c.winfo_width(), 300)
        h = max(c.winfo_height(), 100)

        for i in range(1, 5):
            y = i * h / 5
            c.create_line(0, y, w, y, fill="#e9edf4")

        c.create_text(10, 10, text="CPU", anchor="w", fill=BLUE)
        c.create_text(55, 10, text="RAM", anchor="w", fill=GREEN)

        if len(self.history) < 2:
            c.create_text(w / 2, h / 2,
                          text="Collecting performance data...",
                          fill=GREY)
            return

        for idx, color in ((0, BLUE), (1, GREEN)):
            points = []
            for i, pair in enumerate(self.history):
                x = 5 + i * (w - 10) / (len(self.history) - 1)
                y = h - 5 - pair[idx] * (h - 15) / 100
                points.extend((x, y))
            c.create_line(*points, fill=color, width=2, smooth=True)

    def refresh_health(self):
        ram = psutil.virtual_memory()
        lines = [
            "WACAT BASIC HEALTH REPORT",
            "=" * 32,
            "Time: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            f"CPU usage: {psutil.cpu_percent(interval=0.2):.1f}%",
            f"RAM usage: {ram.percent:.1f}%",
            f"RAM available: {ram.available / 2**30:.2f} GB",
            "Memory status: " + ("OK" if ram.percent < 80 else "HIGH USAGE"),
            "",
            "STORAGE CHECK"
        ]
        for part in psutil.disk_partitions(all=False):
            try:
                d = psutil.disk_usage(part.mountpoint)
                lines.append(
                    f"{part.device} {d.percent:.0f}% used, "
                    f"{d.free / 2**30:.1f} GB free"
                )
                if d.percent >= 90:
                    lines.append("  NOTICE: Low free disk space")
            except (PermissionError, OSError):
                pass

        lines.extend(["", "BATTERY"])
        try:
            battery = psutil.sensors_battery()
            if battery is None:
                lines.append("Battery status unavailable.")
            else:
                state = "Plugged in" if battery.power_plugged else "On battery"
                lines.append(f"{battery.percent:.0f}% - {state}")
        except Exception:
            lines.append("Battery information unsupported.")

        lines.extend([
            "", "Temperature: not available through standard psutil on many PCs.",
            "This is a software check, not a full hardware diagnostic."
        ])
        self.health_text.delete("1.0", "end")
        self.health_text.insert("1.0", "\n".join(lines))

    def refresh_processes(self):
        for item in self.proc_tree.get_children():
            self.proc_tree.delete(item)

        rows = []
        for p in psutil.process_iter(["pid", "name", "memory_info", "status"]):
            try:
                info = p.info
                rows.append((
                    info["pid"], info.get("name") or "Unknown",
                    info.get("memory_info").rss / 2**20
                    if info.get("memory_info") else 0,
                    info.get("status", ""), p
                ))
            except (psutil.Error, OSError):
                pass

        rows.sort(key=lambda x: x[2], reverse=True)
        for pid, name, memory, status, proc in rows[:250]:
            try:
                cpu = proc.cpu_percent(None)
            except (psutil.Error, OSError):
                cpu = 0
            self.proc_tree.insert("", "end", values=(
                pid, name, f"{cpu:.1f}", f"{memory:.1f}", status
            ))

    def refresh_drives(self):
        for item in self.drive_tree.get_children():
            self.drive_tree.delete(item)
        for part in psutil.disk_partitions(all=False):
            try:
                d = psutil.disk_usage(part.mountpoint)
                self.drive_tree.insert("", "end", values=(
                    part.device, f"{d.total / 2**30:.1f}",
                    f"{d.used / 2**30:.1f}", f"{d.free / 2**30:.1f}",
                    f"{d.percent:.0f}%"
                ))
            except (PermissionError, OSError):
                pass

    def refresh_system(self):
        info = [
            ("Computer", platform.node()),
            ("Operating system", platform.platform()),
            ("Architecture", platform.machine()),
            ("Processor", platform.processor() or "Not reported"),
            ("Physical CPU cores", psutil.cpu_count(logical=False)),
            ("Logical CPU cores", psutil.cpu_count()),
            ("Installed RAM", f"{psutil.virtual_memory().total / 2**30:.2f} GB"),
            ("Python version", platform.python_version()),
            ("Boot time", datetime.fromtimestamp(
                psutil.boot_time()).strftime("%Y-%m-%d %H:%M:%S"))
        ]
        try:
            info.append(("Local IP", socket.gethostbyname(socket.gethostname())))
        except OSError:
            info.append(("Local IP", "Unavailable"))

        self.system_text.delete("1.0", "end")
        self.system_text.insert(
            "1.0", "\n".join(f"{k}: {v}" for k, v in info)
        )

    def write_output(self, message):
        if self.running:
            self.net_output.insert("end", message.rstrip() + "\n")
            self.net_output.see("end")

    def command_worker(self, args, timeout=20):
        self.root.after(0, lambda: self.write_output(
            "\n> " + subprocess.list2cmdline(args)
        ))
        try:
            result = subprocess.run(
                args, capture_output=True, text=True, timeout=timeout,
                errors="replace", shell=False
            )
            output = result.stdout or ""
            if result.stderr:
                output += "\n" + result.stderr
            if not output.strip():
                output = f"Finished with exit code {result.returncode}."
        except Exception as e:
            output = f"Command error: {e}"

        if self.running:
            self.root.after(0, lambda out=output: self.write_output(out))

    def run_command(self, args, timeout=20):
        threading.Thread(target=self.command_worker,
                         args=(args, timeout), daemon=True).start()

    def test_internet(self):
        self.run_command([
            "curl.exe", "-I", "--max-time", "10",
            "https://www.microsoft.com"
        ], 15)

    def check_dns(self):
        self.run_command(["nslookup", "pypi.org"])

    def show_wifi(self):
        self.run_command(["netsh", "wlan", "show", "interfaces"])

    def flush_dns(self):
        if messagebox.askyesno(
            "Flush DNS", "Clear the Windows DNS cache?"
        ):
            self.run_command(["ipconfig", "/flushdns"])

    def python_check(self):
        self.run_command(["python", "--version"])
        self.run_command(["python", "-m", "pip", "--version"])

    def install_package(self):
        name = self.package.get().strip()
        if not name or not all(c.isalnum() or c in "._-" for c in name):
            messagebox.showwarning("Wacat", "Enter a valid package name.")
            return
        if not messagebox.askyesno(
            "Install package",
            f"Install {name} from the configured Python package index?\n"
            "Only install packages you trust."
        ):
            return
        self.run_command(["python", "-m", "pip", "install", name], 180)

    def update_clock(self):
        if self.running:
            self.clock.config(text=datetime.now().strftime("%d %b %Y  %H:%M:%S"))
            self.root.after(1000, self.update_clock)

    def close(self):
        self.running = False
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = WacatPCMonitor(root)
    root.mainloop()
