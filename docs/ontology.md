# Ontologie (concepts métier)

| Terme | Définition | Où dans le code |
|---|---|---|
| Indicateur | Grandeur surveillée affichée sur une ligne : valeur actuelle, min/max/moyenne, courbe. Les 5 du MVP : CPU %, température, fréquence CPU, RAM %, ventilateur. | `app.py` (`SPECS`) |
| Historique | 30 minutes de mesures conservées par indicateur. | `rpimon/monitor.py` (`HISTORY_S`) |
| Fenêtre d'affichage | Durée visible sur la courbe (1, 5 ou 30 min), indépendante de l'historique conservé. | `app.py` (`WINDOWS`) |
| Ventilateur actif | Le ventilateur est demandé ou tourne : état de refroidissement, PWM ou vitesse mesurée > 0. | `rpimon/collectors.py` (`FanReading.active`) |
| Période de 10 s | Intervalle d'agrégation du ventilateur : une seule activation suffit à la marquer. | `rpimon/history.py` (`BucketSeries`) |
| Mesure indisponible | Capteur absent ou illisible : affiché `--`, jamais compté comme 0. | `rpimon/history.py` (NaN) |
