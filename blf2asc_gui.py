#!/usr/bin/python

import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog
from tkinter import messagebox
from tkinter import ttk

import can

from blf2asc import format_message


class Blf2AscGui(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("BLF to ASC Converter")
        self.geometry("780x560")

        self.input_file = tk.StringVar()
        self.output_file = tk.StringVar()
        self.status = tk.StringVar(value="Load a BLF file to start.")
        self.progress_text = tk.StringVar(value="")

        self.channels = []
        self.can_ids = []
        self.queue = queue.Queue()
        self.worker = None

        self.create_widgets()
        self.after(100, self.process_queue)

    def create_widgets(self):
        file_frame = ttk.LabelFrame(self, text="Files")
        file_frame.pack(fill="x", padx=10, pady=10)

        ttk.Label(file_frame, text="BLF file").grid(row=0, column=0, sticky="w", padx=8, pady=6)
        ttk.Entry(file_frame, textvariable=self.input_file).grid(
            row=0, column=1, sticky="ew", padx=8, pady=6
        )
        ttk.Button(file_frame, text="Load BLF...", command=self.select_input_file).grid(
            row=0, column=2, padx=8, pady=6
        )

        ttk.Label(file_frame, text="ASC output").grid(row=1, column=0, sticky="w", padx=8, pady=6)
        ttk.Entry(file_frame, textvariable=self.output_file).grid(
            row=1, column=1, sticky="ew", padx=8, pady=6
        )
        ttk.Button(file_frame, text="Browse...", command=self.select_output_file).grid(
            row=1, column=2, padx=8, pady=6
        )

        file_frame.columnconfigure(1, weight=1)

        selection_frame = ttk.Frame(self)
        selection_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        channel_frame = ttk.LabelFrame(selection_frame, text="Channels")
        channel_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))

        self.channel_list = tk.Listbox(channel_frame, selectmode=tk.EXTENDED, exportselection=False)
        self.channel_list.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        channel_scroll = ttk.Scrollbar(channel_frame, orient="vertical", command=self.channel_list.yview)
        channel_scroll.pack(side="right", fill="y", padx=(0, 8), pady=8)
        self.channel_list.config(yscrollcommand=channel_scroll.set)

        id_frame = ttk.LabelFrame(selection_frame, text="CAN IDs")
        id_frame.pack(side="left", fill="both", expand=True, padx=(5, 0))

        self.id_list = tk.Listbox(id_frame, selectmode=tk.EXTENDED, exportselection=False)
        self.id_list.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        id_scroll = ttk.Scrollbar(id_frame, orient="vertical", command=self.id_list.yview)
        id_scroll.pack(side="right", fill="y", padx=(0, 8), pady=8)
        self.id_list.config(yscrollcommand=id_scroll.set)

        button_frame = ttk.Frame(self)
        button_frame.pack(fill="x", padx=10, pady=(0, 10))

        self.select_all_button = ttk.Button(
            button_frame, text="Select All", command=self.select_all, state="disabled"
        )
        self.select_all_button.pack(side="left")

        self.clear_button = ttk.Button(
            button_frame, text="Clear Selection", command=self.clear_selection, state="disabled"
        )
        self.clear_button.pack(side="left", padx=(8, 0))

        self.convert_button = ttk.Button(
            button_frame, text="Convert", command=self.start_convert, state="disabled"
        )
        self.convert_button.pack(side="right")

        progress_frame = ttk.Frame(self)
        progress_frame.pack(fill="x", padx=10, pady=(0, 10))

        self.progress = ttk.Progressbar(progress_frame, mode="determinate")
        self.progress.pack(fill="x")
        ttk.Label(progress_frame, textvariable=self.progress_text).pack(anchor="w", pady=(4, 0))
        ttk.Label(self, textvariable=self.status).pack(anchor="w", padx=10, pady=(0, 10))

    def select_input_file(self):
        filename = filedialog.askopenfilename(
            title="Select BLF file",
            filetypes=[("BLF files", "*.blf"), ("All files", "*.*")],
        )
        if not filename:
            return

        self.input_file.set(filename)
        base, _ = os.path.splitext(filename)
        self.output_file.set(base + ".asc")
        self.start_scan()

    def select_output_file(self):
        filename = filedialog.asksaveasfilename(
            title="Save ASC file",
            defaultextension=".asc",
            filetypes=[("ASC files", "*.asc"), ("All files", "*.*")],
        )
        if filename:
            self.output_file.set(filename)

    def start_scan(self):
        if self.worker and self.worker.is_alive():
            messagebox.showwarning("Busy", "Please wait for the current operation to finish.")
            return

        self.set_busy(True)
        self.progress["value"] = 0
        self.progress_text.set("")
        self.status.set("Scanning BLF file for channels and CAN IDs...")
        self.channel_list.delete(0, tk.END)
        self.id_list.delete(0, tk.END)

        self.worker = threading.Thread(
            target=self.scan_file_worker, args=(self.input_file.get(),), daemon=True
        )
        self.worker.start()

    def scan_file_worker(self, input_file):
        channels = set()
        can_ids = set()
        read_count = 0

        try:
            reader = can.BLFReader(input_file)
            try:
                file_size = getattr(reader, "file_size", 0) or 0
                for msg in reader:
                    read_count += 1
                    channels.add(msg.channel)
                    can_ids.add(msg.arbitration_id)

                    if read_count % 5000 == 0:
                        self.queue.put(("progress", self.get_reader_percent(reader, file_size)))
                        self.queue.put(("scan_status", read_count))
            finally:
                reader.stop()

            self.queue.put(("scan_done", channels, can_ids, read_count))
        except Exception as exc:
            self.queue.put(("error", str(exc)))

    def start_convert(self):
        if self.worker and self.worker.is_alive():
            messagebox.showwarning("Busy", "Please wait for the current operation to finish.")
            return

        if not self.input_file.get() or not self.output_file.get():
            messagebox.showerror("Missing file", "Please choose both input and output files.")
            return

        selected_channels = self.get_selected_channels()
        selected_ids = self.get_selected_ids()

        if not selected_channels:
            messagebox.showerror("No channels selected", "Select at least one channel.")
            return
        if not selected_ids:
            messagebox.showerror("No CAN IDs selected", "Select at least one CAN ID.")
            return

        self.set_busy(True)
        self.progress["value"] = 0
        self.progress_text.set("")
        self.status.set("Converting BLF to ASC...")

        self.worker = threading.Thread(
            target=self.convert_file_worker,
            args=(self.input_file.get(), self.output_file.get(), selected_channels, selected_ids),
            daemon=True,
        )
        self.worker.start()

    def convert_file_worker(self, input_file, output_file, selected_channels, selected_ids):
        read_count = 0
        written_count = 0
        skipped_count = 0
        start_timestamp = None

        try:
            reader = can.BLFReader(input_file)
            try:
                file_size = getattr(reader, "file_size", 0) or 0
                with open(output_file, "w") as output:
                    for msg in reader:
                        read_count += 1

                        if msg.channel not in selected_channels or msg.arbitration_id not in selected_ids:
                            skipped_count += 1
                        else:
                            if start_timestamp is None:
                                start_timestamp = msg.timestamp

                            output.write(format_message(msg, start_timestamp) + "\n")
                            written_count += 1

                        if read_count % 5000 == 0:
                            self.queue.put(("progress", self.get_reader_percent(reader, file_size)))
                            self.queue.put(
                                ("convert_status", read_count, written_count, skipped_count)
                            )
            finally:
                reader.stop()

            self.queue.put(("convert_done", read_count, written_count, skipped_count))
        except Exception as exc:
            self.queue.put(("error", str(exc)))

    def get_reader_percent(self, reader, file_size):
        if file_size <= 0:
            return 0

        try:
            file_position = reader.file.tell()
        except ValueError:
            file_position = file_size

        return min(file_position / file_size * 100, 100)

    def process_queue(self):
        try:
            while True:
                event = self.queue.get_nowait()
                self.handle_event(event)
        except queue.Empty:
            pass

        self.after(100, self.process_queue)

    def handle_event(self, event):
        event_type = event[0]

        if event_type == "progress":
            self.progress["value"] = event[1]
        elif event_type == "scan_status":
            self.progress_text.set("Scanned {:,} messages".format(event[1]))
        elif event_type == "scan_done":
            _, channels, can_ids, read_count = event
            self.populate_lists(channels, can_ids)
            self.progress["value"] = 100
            self.progress_text.set("Scanned {:,} messages".format(read_count))
            self.status.set(
                "Found {} channels and {} CAN IDs.".format(len(channels), len(can_ids))
            )
            self.set_busy(False)
            self.set_ready_state()
        elif event_type == "convert_status":
            _, read_count, written_count, skipped_count = event
            self.progress_text.set(
                "Read {:,} | Written {:,} | Skipped {:,}".format(
                    read_count, written_count, skipped_count
                )
            )
        elif event_type == "convert_done":
            _, read_count, written_count, skipped_count = event
            self.progress["value"] = 100
            self.progress_text.set(
                "Read {:,} | Written {:,} | Skipped {:,}".format(
                    read_count, written_count, skipped_count
                )
            )
            self.status.set("Conversion complete: {}".format(self.output_file.get()))
            self.set_busy(False)
            self.set_ready_state()
            messagebox.showinfo(
                "Done",
                "Conversion complete.\n\nRead: {:,}\nWritten: {:,}\nSkipped: {:,}".format(
                    read_count, written_count, skipped_count
                ),
            )
        elif event_type == "error":
            self.set_busy(False)
            self.set_ready_state()
            self.status.set("Error: {}".format(event[1]))
            messagebox.showerror("Error", event[1])

    def populate_lists(self, channels, can_ids):
        self.channels = sorted(channels, key=lambda value: str(value))
        self.can_ids = sorted(can_ids)

        self.channel_list.delete(0, tk.END)
        for channel in self.channels:
            self.channel_list.insert(tk.END, "CH {}".format(channel))

        self.id_list.delete(0, tk.END)
        for can_id in self.can_ids:
            self.id_list.insert(tk.END, "0x{:X}".format(can_id))

        self.select_all()

    def select_all(self):
        self.channel_list.select_set(0, tk.END)
        self.id_list.select_set(0, tk.END)

    def clear_selection(self):
        self.channel_list.select_clear(0, tk.END)
        self.id_list.select_clear(0, tk.END)

    def get_selected_channels(self):
        return {self.channels[index] for index in self.channel_list.curselection()}

    def get_selected_ids(self):
        return {self.can_ids[index] for index in self.id_list.curselection()}

    def set_busy(self, is_busy):
        state = "disabled" if is_busy else "normal"
        self.convert_button.config(state="disabled")
        self.select_all_button.config(state=state if self.channels else "disabled")
        self.clear_button.config(state=state if self.channels else "disabled")

    def set_ready_state(self):
        has_scan_results = bool(self.channels and self.can_ids)
        state = "normal" if has_scan_results else "disabled"
        self.convert_button.config(state=state)
        self.select_all_button.config(state=state)
        self.clear_button.config(state=state)


if __name__ == "__main__":
    Blf2AscGui().mainloop()
