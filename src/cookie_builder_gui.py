#!/usr/bin/env python3
"""Basic desktop GUI for Cookie-Builder."""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageTk

from cookie_builder import load_mask
import cookie_builder_core as core


class CookieBuilderGUI(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Cookie-Builder")
        self.geometry("980x680")
        self.minsize(820, 600)

        self.input_path: Path | None = None
        self.preview_image: ImageTk.PhotoImage | None = None

        self.size_mm = tk.DoubleVar(value=80.0)
        self.wall_mm = tk.DoubleVar(value=1.2)
        self.cutter_height_mm = tk.DoubleVar(value=12.0)
        self.emboss_mm = tk.DoubleVar(value=1.0)
        self.base_mm = tk.DoubleVar(value=2.0)
        self.simplify_mm = tk.DoubleVar(value=0.25)
        self.threshold = tk.IntVar(value=128)
        self.invert = tk.BooleanVar(value=False)

        self._build_layout()

    def _build_layout(self) -> None:
        main = ttk.Frame(self, padding=12)
        main.pack(fill="both", expand=True)

        controls = ttk.LabelFrame(main, text="Einstellungen", padding=12)
        controls.pack(side="left", fill="y", padx=(0, 12))

        preview = ttk.LabelFrame(main, text="Bildvorschau", padding=12)
        preview.pack(side="right", fill="both", expand=True)

        ttk.Button(controls, text="Bild auswählen", command=self.select_image).pack(fill="x")
        self.input_label = ttk.Label(controls, text="Keine Datei", wraplength=220)
        self.input_label.pack(fill="x", pady=(6, 12))

        fields = (
            ("Größe (mm)", self.size_mm),
            ("Wandstärke (mm)", self.wall_mm),
            ("Kantenhöhe (mm)", self.cutter_height_mm),
            ("Prägehöhe (mm)", self.emboss_mm),
            ("Sockelhöhe (mm)", self.base_mm),
            ("Konturvereinfachung (mm)", self.simplify_mm),
            ("Schwellenwert", self.threshold),
        )
        for label, variable in fields:
            ttk.Label(controls, text=label).pack(anchor="w", pady=(4, 0))
            ttk.Entry(controls, textvariable=variable).pack(fill="x")

        ttk.Checkbutton(controls, text="Maske invertieren", variable=self.invert).pack(anchor="w", pady=(10, 0))
        ttk.Button(controls, text="Maskenvorschau", command=self.show_preview).pack(fill="x", pady=(12, 6))
        ttk.Button(controls, text="STL erzeugen", command=self.generate).pack(fill="x")

        self.status = tk.StringVar(value="Bereit")
        ttk.Label(controls, textvariable=self.status, foreground="#555", wraplength=220).pack(fill="x", pady=(12, 0))

        self.preview_label = ttk.Label(preview)
        self.preview_label.pack(fill="both", expand=True)

    def select_image(self) -> None:
        filename = filedialog.askopenfilename(
            title="Motiv auswählen",
            filetypes=[("Bilder", "*.png *.jpg *.jpeg *.bmp *.tif *.tiff"), ("Alle Dateien", "*.*")],
        )
        if not filename:
            return

        self.input_path = Path(filename)
        self.input_label.config(text=self.input_path.name)
        self.show_preview()

    def show_preview(self) -> None:
        if self.input_path is None:
            messagebox.showinfo("Kein Bild", "Bitte zuerst ein Bild auswählen.")
            return

        try:
            mask = load_mask(self.input_path, self.threshold.get(), self.invert.get())
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                raise ValueError("Keine Kontur gefunden")

            preview = cv2.cvtImage if False else cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
            largest = max(contours, key=cv2.contourArea)
            cv2.drawContours(preview, [largest], -1, (0, 0, 255), 2)

            rgb = cv2.cvtColor(preview, cv2.COLOR_BGR2RGB)
            image = Image.fromarray(rgb)
            image.thumbnail((650, 520))
            self.preview_image = ImageTk.PhotoImage(image)
            self.preview_label.config(image=self.preview_image)
            self.status.set("Maskenvorschau aktualisiert")
        except Exception as exc:
            messagebox.showerror("Fehler", str(exc))

    def generate(self) -> None:
        if self.input_path is None:
            messagebox.showinfo("Kein Bild", "Bitte zuerst ein Bild auswählen.")
            return

        output = filedialog.asksaveasfilename(
            title="STL speichern",
            defaultextension=".stl",
            filetypes=[("STL-Datei", "*.stl")],
        )
        if not output:
            return

        try:
            if self.emboss_mm.get() < 0:
                raise ValueError("Prägehöhe darf nicht negativ sein")
            if self.cutter_height_mm.get() <= self.emboss_mm.get():
                raise ValueError("Die Kantenhöhe muss größer als die Prägehöhe sein")

            mask = load_mask(self.input_path, self.threshold.get(), self.invert.get())
            result = core.generate_model(
                mask=mask,
                size_mm=self.size_mm.get(),
                wall_mm=self.wall_mm.get(),
                cutter_height_mm=self.cutter_height_mm.get(),
                emboss_mm=self.emboss_mm.get(),
                base_mm=self.base_mm.get(),
                simplify_mm=self.simplify_mm.get(),
            )

            output_path = Path(output)
            result.mesh.export(output_path)

            warning_text = ""
            if result.warnings:
                warning_text = "\n\nHinweise:\n" + "\n".join("• " + item for item in result.warnings)

            messagebox.showinfo(
                "Fertig",
                f"STL wurde gespeichert:\n{output_path}\n\n"
                f"Dreiecke: {len(result.mesh.faces):,}\n"
                f"Prägeselemente: {len(result.emboss_geometries)}"
                + warning_text,
            )
            self.status.set(f"Gespeichert: {output_path.name}")
        except Exception as exc:
            messagebox.showerror("Fehler", str(exc))
            self.status.set("Erzeugung fehlgeschlagen")


def main() -> int:
    app = CookieBuilderGUI()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
