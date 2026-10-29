# Bonnes pratiques détectées

- **Textual / mise en page** : ne pas combiner `height: 1fr` et `min-height` sur les lignes empilées ; si le terminal est plus court que la somme des minimums, chaque ligne prend presque toute la hauteur (constaté sur le Pi).
- **Textual / tests** : tester l'UI en headless avec `App.run_test(size=...)` à plusieurs hauteurs de terminal, pas seulement une grande.
- **Graphiques / échelle auto** : une courbe pleine (aires) sur une échelle automatique exagère les valeurs (47 °C paraît « presque plein ») ; préférer une ligne.
- **Capteurs Pi** : chemins hwmon numérotés de façon instable, les chercher par le fichier `name` (`pwmfan`, `cpu_thermal`) et redétecter après un échec de lecture.
- **Ventilateur** : `pwm1` et `fan1_input` peuvent valoir 0 alors qu'il tourne ; croiser avec `cooling_device*/cur_state`.
- **Collecte** : thread séparé de l'UI ; un capteur qui lève une exception donne `None`, jamais un arrêt de la collecte.
- **Fichiers non versionnés** : captures d'écran et `.DS_Store` ignorés par git.
