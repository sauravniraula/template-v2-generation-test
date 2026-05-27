"use client";

import { useState } from "react";
import SlideRenderer from "@/components/SlideRenderer";
import type { SlideLayout } from "@/types/layout";

const DASHBOARD_IMAGE =
  "data:image/svg+xml,%3Csvg%20xmlns%3D%27http%3A//www.w3.org/2000/svg%27%20viewBox%3D%270%200%20420%20260%27%3E%3Crect%20width%3D%27420%27%20height%3D%27260%27%20rx%3D%2728%27%20fill%3D%27%23111827%27/%3E%3Cpath%20d%3D%27M0%20210%20C85%20172%20122%20112%20208%20140%20C290%20166%20320%2058%20420%2036%20L420%20260%20L0%20260Z%27%20fill%3D%27%232563EB%27%20opacity%3D%27.72%27/%3E%3Ccircle%20cx%3D%27328%27%20cy%3D%2784%27%20r%3D%2752%27%20fill%3D%27%23F59E0B%27%20opacity%3D%27.9%27/%3E%3Crect%20x%3D%2740%27%20y%3D%2748%27%20width%3D%27188%27%20height%3D%2718%27%20rx%3D%279%27%20fill%3D%27%23F8FAFC%27%20opacity%3D%27.92%27/%3E%3Crect%20x%3D%2740%27%20y%3D%2784%27%20width%3D%27252%27%20height%3D%2710%27%20rx%3D%275%27%20fill%3D%27%23CBD5E1%27%20opacity%3D%27.88%27/%3E%3Crect%20x%3D%2740%27%20y%3D%27110%27%20width%3D%27216%27%20height%3D%2710%27%20rx%3D%275%27%20fill%3D%27%23CBD5E1%27%20opacity%3D%27.74%27/%3E%3C/svg%3E";

const INITIAL_LAYOUTS: SlideLayout[] = [
  {
    id: "operating_dashboard",
    description: "Complex dashboard layout composed with relative renderer elements",
    components: [
      {
        id: "canvas_background",
        descritpion: "Layered slide background with decorative primitive elements.",
        position: { x: 0, y: 0 },
        size: { width: 1280, height: 720 },
        elements: [
          {
            type: "rectangle",
            fixed: true,
            position: { x: 0, y: 0 },
            size: { width: 1280, height: 720 },
            fill: { color: "#F8FAFC" },
          },
          {
            type: "rectangle",
            fixed: true,
            position: { x: 0, y: 640 },
            size: { width: 1280, height: 80 },
            fill: { color: "#E0F2FE", opacity: 0.65 },
          },
          {
            type: "ellipse",
            fixed: true,
            position: { x: 1016, y: -62 },
            size: { width: 260, height: 260 },
            fill: { color: "#A7F3D0", opacity: 0.48 },
          },
          {
            type: "ellipse",
            fixed: true,
            position: { x: -74, y: 452 },
            size: { width: 210, height: 210 },
            fill: { color: "#FDE68A", opacity: 0.52 },
          },
          {
            type: "line",
            fixed: true,
            position: { x: 64, y: 626 },
            size: { width: 1152, height: 1 },
            stroke: { color: "#CBD5E1", width: 1, dash: [8, 8] },
          },
        ],
      },
      {
        id: "header_bar",
        descritpion: "Header assembled with a relative flex layout.",
        position: { x: 64, y: 36 },
        size: { width: 1152, height: 72 },
        elements: [
          {
            type: "flex",
            fixed: true,
            position: { x: 0, y: 0 },
            size: { width: 1152, height: 72 },
            direction: "row",
            alignItems: "stretch",
            gap: 18,
            children: [
              {
                type: "container",
                fixed: true,
                size: { width: 260, height: 72 },
                fill: { color: "#111827" },
                borderRadius: { tl: 8, tr: 8, br: 8, bl: 8 },
                padding: { top: 14, right: 18, bottom: 14, left: 18 },
                child: {
                  type: "group",
                  fixed: true,
                  position: { x: 18, y: 14 },
                  size: { width: 224, height: 44 },
                  children: [
                    {
                      type: "ellipse",
                      fixed: true,
                      position: { x: 0, y: 7 },
                      size: { width: 30, height: 30 },
                      fill: { color: "#22C55E" },
                    },
                    {
                      type: "text",
                      fixed: false,
                      position: { x: 44, y: 0 },
                      size: { width: 170, height: 20 },
                      font: { size: 16, color: "#FFFFFF", bold: true },
                      runs: [{ text: "Northstar Ops" }],
                    },
                    {
                      type: "text",
                      fixed: false,
                      position: { x: 44, y: 24 },
                      size: { width: 170, height: 18 },
                      font: {
                        size: 11,
                        color: "#A7F3D0",
                        bold: true,
                        letterSpacing: 1.2,
                        wrap: "none",
                      },
                      runs: [{ text: "LIVE BOARD" }],
                    },
                  ],
                },
              },
              {
                type: "text",
                fixed: false,
                font: { size: 26, color: "#0F172A", bold: true },
                alignment: {
                  vertical: "middle",
                },
                runs: [{ text: "Revenue command center" }],
                minLength: 12,
                maxLength: 40,
              },
              {
                type: "container",
                fixed: true,
                size: { width: 176, height: 72 },
                fill: { color: "#FFFFFF" },
                stroke: { color: "#CBD5E1", width: 1 },
                borderRadius: { tl: 8, tr: 8, br: 8, bl: 8 },
                padding: { top: 12, right: 14, bottom: 12, left: 14 },
                child: {
                  type: "group",
                  fixed: true,
                  position: { x: 14, y: 12 },
                  size: { width: 148, height: 48 },
                  children: [
                    {
                      type: "text",
                      fixed: false,
                      position: { x: 0, y: 0 },
                      size: { width: 148, height: 18 },
                      font: { size: 11, color: "#64748B", bold: true },
                      runs: [{ text: "LAST SYNC" }],
                    },
                    {
                      type: "text",
                      fixed: false,
                      position: { x: 0, y: 22 },
                      size: { width: 148, height: 24 },
                      font: { size: 18, color: "#0F172A", bold: true },
                      runs: [{ text: "Today 09:45" }],
                    },
                  ],
                },
              },
            ],
          },
        ],
      },
      {
        id: "hero_story",
        descritpion: "Hero section using a grid for copy, media, and an overlaid trend group.",
        position: { x: 64, y: 132 },
        size: { width: 640, height: 246 },
        elements: [
          {
            type: "grid",
            fixed: false,
            position: { x: 0, y: 0 },
            size: { width: 640, height: 246 },
            columns: 2,
            columnGap: 18,
            children: [
              {
                type: "container",
                fixed: false,
                fill: { color: "#FFFFFF" },
                stroke: { color: "#E2E8F0", width: 1 },
                borderRadius: { tl: 8, tr: 8, br: 8, bl: 8 },
                shadow: {
                  color: "#0F172A",
                  opacity: 0.06,
                  blur: 18,
                  offsetY: 10,
                },
                padding: { top: 24, right: 24, bottom: 24, left: 24 },
                child: {
                  type: "flex",
                  fixed: false,
                  position: { x: 24, y: 24 },
                  size: { width: 261, height: 198 },
                  direction: "column",
                  gap: 12,
                  children: [
                    {
                      type: "text",
                      fixed: false,
                      size: { width: 261, height: 22 },
                      font: {
                        size: 12,
                        color: "#2563EB",
                        bold: true,
                        letterSpacing: 1.1,
                        wrap: "none",
                      },
                      runs: [{ text: "EXECUTIVE SUMMARY" }],
                    },
                    {
                      type: "text",
                      fixed: false,
                      size: { width: 261, height: 78 },
                      font: {
                        size: 28,
                        color: "#0F172A",
                        bold: true,
                        lineHeight: 34,
                      },
                      runs: [{ text: "Expansion quality is improving faster than volume." }],
                      minLength: 24,
                      maxLength: 80,
                    },
                    {
                      type: "text",
                      fixed: false,
                      size: { width: 261, height: 62 },
                      font: { size: 15, color: "#475569", lineHeight: 22 },
                      runs: [
                        {
                          text: "Attach rate, sales cycle compression, and partner-sourced pipeline moved in the same direction for the first time this year.",
                        },
                      ],
                      minLength: 60,
                      maxLength: 180,
                    },
                    {
                      type: "line",
                      fixed: true,
                      size: { width: 261, height: 1 },
                      stroke: { color: "#CBD5E1", width: 1 },
                    },
                  ],
                },
              },
              {
                type: "group",
                fixed: false,
                position: { x: 0, y: 0 },
                size: { width: 310, height: 246 },
                children: [
                  {
                    type: "image",
                    fixed: true,
                    position: { x: 0, y: 0 },
                    size: { width: 310, height: 246 },
                    data: DASHBOARD_IMAGE,
                    name: "Abstract dashboard preview",
                    fit: "cover",
                    borderRadius: { tl: 8, tr: 8, br: 8, bl: 8 },
                  },
                  {
                    type: "container",
                    fixed: true,
                    position: { x: 24, y: 142 },
                    size: { width: 166, height: 78 },
                    fill: { color: "#FFFFFF", opacity: 0.9 },
                    borderRadius: { tl: 8, tr: 8, br: 8, bl: 8 },
                    padding: { top: 10, right: 12, bottom: 10, left: 12 },
                    child: {
                      type: "chart",
                      fixed: false,
                      position: { x: 12, y: 10 },
                      size: { width: 142, height: 58 },
                      chartType: "line",
                      color: "#16A34A",
                      axisColor: "#CBD5E1",
                      data: [
                        { label: "Jan", value: 18 },
                        { label: "Feb", value: 26 },
                        { label: "Mar", value: 22 },
                        { label: "Apr", value: 36 },
                        { label: "May", value: 44 },
                      ],
                    },
                  },
                ],
              },
            ],
          },
        ],
      },
      {
        id: "metric_system",
        descritpion: "Relative grid of metric cards with nested donut charts.",
        position: { x: 728, y: 132 },
        size: { width: 488, height: 246 },
        elements: [
          {
            type: "grid",
            fixed: false,
            position: { x: 0, y: 0 },
            size: { width: 488, height: 246 },
            columns: 2,
            rows: 2,
            gap: 16,
            children: [
              {
                type: "container",
                fixed: false,
                fill: { color: "#FFFFFF" },
                stroke: { color: "#E2E8F0", width: 1 },
                borderRadius: { tl: 8, tr: 8, br: 8, bl: 8 },
                padding: { top: 16, right: 16, bottom: 16, left: 16 },
                child: {
                  type: "group",
                  fixed: false,
                  position: { x: 16, y: 16 },
                  size: { width: 204, height: 91 },
                  children: [
                    {
                      type: "text",
                      fixed: false,
                      position: { x: 0, y: 0 },
                      size: { width: 128, height: 20 },
                      font: { size: 12, color: "#64748B", bold: true },
                      runs: [{ text: "NET REVENUE" }],
                    },
                    {
                      type: "text",
                      fixed: false,
                      position: { x: 0, y: 28 },
                      size: { width: 128, height: 34 },
                      font: { size: 30, color: "#0F172A", bold: true },
                      runs: [{ text: "$8.4M" }],
                    },
                    {
                      type: "chart",
                      fixed: false,
                      position: { x: 142, y: 8 },
                      size: { width: 56, height: 56 },
                      chartType: "donut",
                      color: "#2563EB",
                      data: [
                        { label: "Won", value: 72, color: "#2563EB" },
                        { label: "Open", value: 28, color: "#E2E8F0" },
                      ],
                    },
                  ],
                },
              },
              {
                type: "container",
                fixed: false,
                fill: { color: "#FFFFFF" },
                stroke: { color: "#E2E8F0", width: 1 },
                borderRadius: { tl: 8, tr: 8, br: 8, bl: 8 },
                padding: { top: 16, right: 16, bottom: 16, left: 16 },
                child: {
                  type: "group",
                  fixed: false,
                  position: { x: 16, y: 16 },
                  size: { width: 204, height: 91 },
                  children: [
                    {
                      type: "text",
                      fixed: false,
                      position: { x: 0, y: 0 },
                      size: { width: 128, height: 20 },
                      font: { size: 12, color: "#64748B", bold: true },
                      runs: [{ text: "RETENTION" }],
                    },
                    {
                      type: "text",
                      fixed: false,
                      position: { x: 0, y: 28 },
                      size: { width: 128, height: 34 },
                      font: { size: 30, color: "#0F172A", bold: true },
                      runs: [{ text: "94%" }],
                    },
                    {
                      type: "chart",
                      fixed: false,
                      position: { x: 142, y: 8 },
                      size: { width: 56, height: 56 },
                      chartType: "donut",
                      color: "#16A34A",
                      data: [
                        { label: "Kept", value: 94, color: "#16A34A" },
                        { label: "Lost", value: 6, color: "#E2E8F0" },
                      ],
                    },
                  ],
                },
              },
              {
                type: "container",
                fixed: false,
                fill: { color: "#FFFFFF" },
                stroke: { color: "#E2E8F0", width: 1 },
                borderRadius: { tl: 8, tr: 8, br: 8, bl: 8 },
                padding: { top: 16, right: 16, bottom: 16, left: 16 },
                child: {
                  type: "group",
                  fixed: false,
                  position: { x: 16, y: 16 },
                  size: { width: 204, height: 91 },
                  children: [
                    {
                      type: "text",
                      fixed: false,
                      position: { x: 0, y: 0 },
                      size: { width: 128, height: 20 },
                      font: { size: 12, color: "#64748B", bold: true },
                      runs: [{ text: "CAC PAYBACK" }],
                    },
                    {
                      type: "text",
                      fixed: false,
                      position: { x: 0, y: 28 },
                      size: { width: 128, height: 34 },
                      font: { size: 30, color: "#0F172A", bold: true },
                      runs: [{ text: "7.8" }],
                    },
                    {
                      type: "text",
                      fixed: false,
                      position: { x: 0, y: 66 },
                      size: { width: 170, height: 20 },
                      font: { size: 12, color: "#EA580C", bold: true },
                      runs: [{ text: "months, improving" }],
                    },
                  ],
                },
              },
              {
                type: "container",
                fixed: false,
                fill: { color: "#FFFFFF" },
                stroke: { color: "#E2E8F0", width: 1 },
                borderRadius: { tl: 8, tr: 8, br: 8, bl: 8 },
                padding: { top: 16, right: 16, bottom: 16, left: 16 },
                child: {
                  type: "group",
                  fixed: false,
                  position: { x: 16, y: 16 },
                  size: { width: 204, height: 91 },
                  children: [
                    {
                      type: "text",
                      fixed: false,
                      position: { x: 0, y: 0 },
                      size: { width: 128, height: 20 },
                      font: { size: 12, color: "#64748B", bold: true },
                      runs: [{ text: "PIPELINE" }],
                    },
                    {
                      type: "text",
                      fixed: false,
                      position: { x: 0, y: 28 },
                      size: { width: 128, height: 34 },
                      font: { size: 30, color: "#0F172A", bold: true },
                      runs: [{ text: "$18M" }],
                    },
                    {
                      type: "text",
                      fixed: false,
                      position: { x: 0, y: 66 },
                      size: { width: 170, height: 20 },
                      font: { size: 12, color: "#7C3AED", bold: true },
                      runs: [{ text: "3.4x quarter target" }],
                    },
                  ],
                },
              },
            ],
          },
        ],
      },
      {
        id: "workstream_panel",
        descritpion: "Relative flex panel with repeated list-view milestones and bullet notes.",
        position: { x: 64, y: 404 },
        size: { width: 492, height: 248 },
        elements: [
          {
            type: "container",
            fixed: false,
            position: { x: 0, y: 0 },
            size: { width: 492, height: 248 },
            fill: { color: "#FFFFFF" },
            stroke: { color: "#E2E8F0", width: 1 },
            borderRadius: { tl: 8, tr: 8, br: 8, bl: 8 },
            padding: { top: 22, right: 22, bottom: 22, left: 22 },
            child: {
              type: "flex",
              fixed: false,
              position: { x: 22, y: 22 },
              size: { width: 448, height: 204 },
              direction: "row",
              gap: 22,
              children: [
                {
                  type: "list-view",
                  fixed: false,
                  size: { width: 210, height: 204 },
                  direction: "column",
                  gap: 12,
                  count: 4,
                  minCount: 3,
                  maxCount: 6,
                  item: {
                    type: "container",
                    fixed: false,
                    fill: { color: "#F8FAFC" },
                    stroke: { color: "#E2E8F0", width: 1 },
                    borderRadius: { tl: 8, tr: 8, br: 8, bl: 8 },
                    child: {
                      type: "group",
                      fixed: false,
                      position: { x: 10, y: 8 },
                      size: { width: 190, height: 36 },
                      children: [
                        {
                          type: "ellipse",
                          fixed: true,
                          position: { x: 0, y: 8 },
                          size: { width: 18, height: 18 },
                          fill: { color: "#2563EB" },
                        },
                        {
                          type: "text",
                          fixed: false,
                          position: { x: 30, y: 0 },
                          size: { width: 150, height: 18 },
                          font: { size: 13, color: "#0F172A", bold: true },
                          runs: [{ text: "Milestone active" }],
                        },
                        {
                          type: "text",
                          fixed: false,
                          position: { x: 30, y: 20 },
                          size: { width: 150, height: 16 },
                          font: { size: 11, color: "#64748B" },
                          runs: [{ text: "Owner review pending" }],
                        },
                      ],
                    },
                  },
                },
                {
                  type: "container",
                  fixed: false,
                  fill: { color: "#FEFCE8" },
                  stroke: { color: "#FDE68A", width: 1 },
                  borderRadius: { tl: 8, tr: 8, br: 8, bl: 8 },
                  padding: { top: 18, right: 18, bottom: 18, left: 18 },
                  child: {
                    type: "text-list",
                    fixed: false,
                    position: { x: 18, y: 18 },
                    size: { width: 180, height: 168 },
                    font: {
                      size: 14,
                      color: "#713F12",
                      lineHeight: 22,
                    },
                    marker: "bullet",
                    items: [
                      { type: "text", text: "Protect enterprise onboarding capacity." },
                      { type: "text", text: "Move partner launch to legal review." },
                      { type: "text", text: "Resolve search spend attribution gap." },
                    ],
                    minItems: 3,
                    maxItems: 5,
                    minItemLength: 18,
                    maxItemLength: 80,
                  },
                },
              ],
            },
          },
        ],
      },
      {
        id: "channel_matrix",
        descritpion: "Grid-view region cards paired with a summary table and bar chart.",
        position: { x: 584, y: 404 },
        size: { width: 632, height: 248 },
        elements: [
          {
            type: "flex",
            fixed: false,
            position: { x: 0, y: 0 },
            size: { width: 632, height: 248 },
            direction: "row",
            gap: 18,
            children: [
              {
                type: "grid-view",
                fixed: false,
                size: { width: 248, height: 248 },
                columns: 2,
                rows: 2,
                gap: 14,
                count: 4,
                minCount: 4,
                maxCount: 6,
                item: {
                  type: "container",
                  fixed: false,
                  fill: { color: "#FFFFFF" },
                  stroke: { color: "#E2E8F0", width: 1 },
                  borderRadius: { tl: 8, tr: 8, br: 8, bl: 8 },
                  padding: { top: 14, right: 14, bottom: 14, left: 14 },
                  child: {
                    type: "group",
                    fixed: false,
                    position: { x: 14, y: 14 },
                    size: { width: 83, height: 83 },
                    children: [
                      {
                        type: "rectangle",
                        fixed: true,
                        position: { x: 0, y: 0 },
                        size: { width: 34, height: 6 },
                        fill: { color: "#16A34A" },
                        borderRadius: { tl: 3, tr: 3, br: 3, bl: 3 },
                      },
                      {
                        type: "text",
                        fixed: false,
                        position: { x: 0, y: 18 },
                        size: { width: 83, height: 22 },
                        font: { size: 14, color: "#0F172A", bold: true },
                        runs: [{ text: "Region" }],
                      },
                      {
                        type: "text",
                        fixed: false,
                        position: { x: 0, y: 46 },
                        size: { width: 83, height: 30 },
                        font: { size: 24, color: "#0F172A", bold: true },
                        runs: [{ text: "86" }],
                      },
                    ],
                  },
                },
              },
              {
                type: "container",
                fixed: false,
                fill: { color: "#FFFFFF" },
                stroke: { color: "#E2E8F0", width: 1 },
                borderRadius: { tl: 8, tr: 8, br: 8, bl: 8 },
                padding: { top: 18, right: 18, bottom: 18, left: 18 },
                child: {
                  type: "group",
                  fixed: false,
                  position: { x: 18, y: 18 },
                  size: { width: 330, height: 212 },
                  children: [
                    {
                      type: "chart",
                      fixed: false,
                      position: { x: 0, y: 0 },
                      size: { width: 330, height: 112 },
                      chartType: "bar",
                      title: "Channel mix",
                      color: "#2563EB",
                      axisColor: "#CBD5E1",
                      labelColor: "#334155",
                      data: [
                        { label: "Web", value: 42, color: "#2563EB" },
                        { label: "Sales", value: 35, color: "#16A34A" },
                        { label: "Partner", value: 28, color: "#7C3AED" },
                        { label: "Field", value: 16, color: "#F59E0B" },
                      ],
                    },
                    {
                      type: "table",
                      fixed: false,
                      position: { x: 0, y: 128 },
                      size: { width: 330, height: 84 },
                      columns: [
                        {
                          text: "Motion",
                          fill: { color: "#F1F5F9" },
                          stroke: { color: "#CBD5E1", width: 1 },
                        },
                        {
                          text: "QoQ",
                          fill: { color: "#F1F5F9" },
                          stroke: { color: "#CBD5E1", width: 1 },
                        },
                        {
                          text: "Risk",
                          fill: { color: "#F1F5F9" },
                          stroke: { color: "#CBD5E1", width: 1 },
                        },
                      ],
                      rows: [
                        [
                          { text: "Inbound", stroke: { color: "#E2E8F0", width: 1 } },
                          { text: "+14%", stroke: { color: "#E2E8F0", width: 1 } },
                          { text: "Low", stroke: { color: "#E2E8F0", width: 1 } },
                        ],
                        [
                          { text: "Partner", stroke: { color: "#E2E8F0", width: 1 } },
                          { text: "+22%", stroke: { color: "#E2E8F0", width: 1 } },
                          { text: "Med", stroke: { color: "#E2E8F0", width: 1 } },
                        ],
                      ],
                    },
                  ],
                },
              },
            ],
          },
        ],
      },
    ],
  },
];

interface LayoutHistory {
  past: SlideLayout[][];
  present: SlideLayout[];
  future: SlideLayout[][];
}

export default function App() {
  const [layoutHistory, setLayoutHistory] = useState<LayoutHistory>({
    past: [],
    present: INITIAL_LAYOUTS,
    future: [],
  });
  const [isStateModalOpen, setIsStateModalOpen] = useState(false);
  const [showComponentMarks, setShowComponentMarks] = useState(false);
  const layouts = layoutHistory.present;
  const currentLayout = layouts[0];
  const canUndo = layoutHistory.past.length > 0;
  const canRedo = layoutHistory.future.length > 0;

  const commitLayouts = (nextLayouts: SlideLayout[]) => {
    setLayoutHistory((currentHistory) => {
      if (currentHistory.present === nextLayouts) {
        return currentHistory;
      }

      return {
        past: [...currentHistory.past, currentHistory.present],
        present: nextLayouts,
        future: [],
      };
    });
  };

  const undoLayoutChange = () => {
    setLayoutHistory((currentHistory) => {
      const previous = currentHistory.past.at(-1);

      if (!previous) {
        return currentHistory;
      }

      return {
        past: currentHistory.past.slice(0, -1),
        present: previous,
        future: [currentHistory.present, ...currentHistory.future],
      };
    });
  };

  const redoLayoutChange = () => {
    setLayoutHistory((currentHistory) => {
      const next = currentHistory.future[0];

      if (!next) {
        return currentHistory;
      }

      return {
        past: [...currentHistory.past, currentHistory.present],
        present: next,
        future: currentHistory.future.slice(1),
      };
    });
  };

  return (
    <main className="min-h-screen overflow-auto bg-slate-100 px-8 py-10 text-slate-950">
      <div className="mx-auto flex w-full max-w-[1360px] flex-col gap-4">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-xl font-semibold">{currentLayout.description}</h1>
            <p className="text-sm text-slate-600">
              {currentLayout.components.length} renderer components
            </p>
          </div>
          <button
            type="button"
            onClick={() => setIsStateModalOpen(true)}
            className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-900 shadow-sm hover:bg-slate-50"
          >
            Get current layout state
          </button>
          <label className="flex cursor-pointer items-center gap-2 rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-900 shadow-sm hover:bg-slate-50">
            <input
              type="checkbox"
              checked={showComponentMarks}
              onChange={(event) => setShowComponentMarks(event.target.checked)}
              className="h-4 w-4"
            />
            <span>Component marks</span>
          </label>
          <button
            type="button"
            onClick={undoLayoutChange}
            disabled={!canUndo}
            className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-900 shadow-sm hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-45"
          >
            Undo
          </button>
          <button
            type="button"
            onClick={redoLayoutChange}
            disabled={!canRedo}
            className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-900 shadow-sm hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-45"
          >
            Redo
          </button>
        </div>
        <SlideRenderer
          layout={currentLayout}
          showComponentBounds={showComponentMarks}
          onLayoutChange={(nextLayout) => {
            commitLayouts(
              layouts.map((layout) =>
                layout.id === nextLayout.id ? nextLayout : layout,
              ),
            );
          }}
        />
      </div>

      {isStateModalOpen ? (
        <div
          role="presentation"
          className="fixed inset-0 z-50 grid place-items-center bg-slate-950/55 p-6"
          onClick={() => setIsStateModalOpen(false)}
        >
          <section
            role="dialog"
            aria-modal="true"
            aria-labelledby="layout-state-title"
            className="flex max-h-[82vh] w-full max-w-5xl flex-col overflow-hidden rounded-md bg-white shadow-2xl"
            onClick={(event) => event.stopPropagation()}
          >
            <header className="flex items-center justify-between gap-4 border-b border-slate-200 px-5 py-4">
              <h2 id="layout-state-title" className="text-base font-semibold">
                Current layouts
              </h2>
              <button
                type="button"
                onClick={() => setIsStateModalOpen(false)}
                className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                Close
              </button>
            </header>
            <pre className="overflow-auto bg-slate-950 p-5 text-xs leading-5 text-slate-100">
              {JSON.stringify(layouts, null, 2)}
            </pre>
          </section>
        </div>
      ) : null}
    </main>
  );
}
