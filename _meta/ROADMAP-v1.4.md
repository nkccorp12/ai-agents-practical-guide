# Roadmap v1.4 (Mai 2026)

Basierend auf sechs destillierten "Process Idea"-Notizen aus laufender Beratungs- und Entwicklungsarbeit.

## Ziel

v1.4 ist eine punktuelle Erweiterung des bestehenden v1.3-Leitfadens. Kein Kapitel-Rewrite, kein neuer struktureller Rahmen. Stattdessen werden sechs konzeptuelle Lücken geschlossen, die sich aus der praktischen Anwendung des Leitfadens ergeben haben: fehlende Architekturschicht (Harness), fehlendes Stack-Gesamtbild, unzureichende RAG-Validierung im Multi-Agent-Kontext, fehlende Produktionsreife-Gates und systematische Skill-Discovery-Methode.

## Story-zu-Abschnitt-Zuordnung

| Process-Idea-Thema           | Abschnitt          | Art            |
|------------------------------|--------------------|----------------|
| Agent-Harness-Konzept        | 3.6 (neu)          | Neuer Abschnitt |
| 2026 Agent-Stack-Modell      | 1.5 (neu)          | Neuer Abschnitt + Hero-Diagramm |
| Multi-Agent-RAG-Validierung  | 8.5 (Erweiterung)  | Ergaenzung bestehender Abschnitt |
| 9-Produktions-Schichten      | 12.8 (neu)         | Neuer Abschnitt |
| Produktions-Monitoring       | 12.9 (neu)         | Neuer Abschnitt |
| Agentic-OS / Skill-Discovery | 4.5 (Erweiterung)  | Ergaenzung bestehender Abschnitt |

## Ansatz: Punktuelle Ergaenzung

Alle sechs Aenderungen sind additiv: bestehende Abschnitte bleiben unveraendert, neue Abschnitte werden an logisch passender Stelle eingefuegt. Keine Nummerierungsverschiebungen in anderen Kapiteln.

Diagramme: zwei neue SVG-Architekturdiagramme (1.5 Hero-Diagramm, 3.6 Harness-Diagramm) in `assets/diagrams/`.

## Spec

Die vollstaendige Implementierungsspezifikation liegt unter:

`docs/superpowers/specs/2026-05-17-agents-v14-update-design.md`

## Abgrenzung zu v1.3

v1.3 hat den Leitfaden von Architektur-Orientierung zu praxistauglichem Produktionsleitfaden umgebaut (Referenz-Implementierungen, erweiterte Sicherheits- und Deployment-Kapitel, Kapitel-9-Rewrite). v1.4 fuellt spezifische konzeptuelle Luecken auf der Basis realer Einsatz-Erfahrungen, ohne den Gesamtaufbau zu veraendern.
