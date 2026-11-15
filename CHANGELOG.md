# Changelog

## 1.2.8
- Correction des données de consommation erronées (Consommation Réseau, HC/HP, Tempo, surplus de production) : l'API ecojoko renvoyait des valeurs dégradées au User-Agent par défaut de Home Assistant, l'intégration envoie désormais son propre User-Agent
- Les capteurs passent à l'état « indisponible » quand l'API ecojoko ne répond plus, au lieu de rester figés sur leur dernière valeur ; les erreurs sont désormais journalisées
- Demande de ré-authentification quand ecojoko refuse le mot de passe, et messages d'erreur précis (identifiants incorrects, connexion impossible) lors de la configuration
- Options : les nouveaux paramètres ne sont enregistrés qu'après validation par ecojoko, et l'intégration n'est rechargée qu'une seule fois
- Température et humidité : rafraîchissement désormais assuré quelle que soit la fréquence choisie (elles n'étaient plus mises à jour à partir de 15 secondes pour l'humidité et de 30 secondes pour la température), et plus aucun appel à ces APIs quand l'option est décochée
- Les données de consommation ne sont plus figées pendant une heure lors du passage à l'heure d'hiver
- Capteurs conformes aux pratiques de Home Assistant (valeur et unité natives) : la conversion d'unité fonctionne désormais, par exemple pour un système configuré en °F
- Les noms des capteurs utilisent désormais les traductions natives de Home Assistant : ils suivent la langue de l'instance (français, anglais, portugais) et l'option de langue de l'intégration disparaît. Les identifiants d'entité, l'historique et les statistiques ne changent pas ; seul le nom affiché perd son tiret (« Ecojoko Consommation Temps Réel » au lieu de « Ecojoko - Consommation Temps Réel »), sauf si vous l'avez personnalisé
- Changer le nom dans les options ne recrée plus les capteurs : entités et appareil sont désormais identifiés par l'entrée de configuration et non par le nom. Les installations existantes sont migrées automatiquement au premier démarrage, en conservant identifiants d'entité, historique et statistiques. Attention : après cette migration, revenir à une version antérieure à la 1.2.8 demande de restaurer une sauvegarde ou de reconfigurer l'intégration
- Un même compte ecojoko ne peut plus être ajouté deux fois
- Une erreur HTTP d'ecojoko (4xx, 5xx) est désormais traitée comme une erreur, y compris à la connexion, au lieu d'être prise pour une réponse valide ; le délai d'attente couvre toute la réponse et les connexions sont toujours libérées
- Ajout des diagnostics de l'intégration (téléchargeables depuis la page de l'appareil ou de l'intégration), identifiants ecojoko masqués, pour faciliter les rapports de bug
- Suppression de deux dépendances non déclarées (`async_timeout`, `pytz`) au profit de la bibliothèque standard de Python

## 1.2.7
- Correction du bug [#118](https://github.com/jmcruvellier/little_monkey/issues/118) : Entités non affichées dans l'appareil Ecojoko

## 1.2.6
- Correction du bug [#116](https://github.com/jmcruvellier/little_monkey/issues/116) : Problème de reporting sur la page energie

## 1.2.5
- Correction du bug [#110](https://github.com/jmcruvellier/little_monkey/issues/110) : Surplus de production attendu en positif et plus en négatif
- Fix URL dans le json des traductions (nouvelle règle de validation de la qualité du code)

## 1.2.4
- Correction du bug [#101](https://github.com/jmcruvellier/little_monkey/issues/101)

## 1.2.3
- Correction du bug [#93](https://github.com/jmcruvellier/little_monkey/issues/93)
- Ajout du portugais à la liste des langues disponibles [#80](https://github.com/jmcruvellier/little_monkey/pull/80) [#88](https://github.com/jmcruvellier/little_monkey/pull/88) [#89](https://github.com/jmcruvellier/little_monkey/pull/89)

## 1.2.2
- Correction du bug [#74](https://github.com/jmcruvellier/little_monkey/issues/74)

## 1.2.1
- Correction du bug [#78](https://github.com/jmcruvellier/little_monkey/issues/78)

## 1.2.0
- Optimisation majeure du code et des performances
- Suppression des capteurs introduits en v1.1.0, basés sur les APIs Measurements d'ecojoko
- Correction du bug [#58](https://github.com/jmcruvellier/little_monkey/issues/58)

## 1.1.0
- Nouveaux capteurs basés sur les APIs Measurements d'ecojoko
- Améliorations de performance et corrections de bugs mineurs
- Correction du bug [#58](https://github.com/jmcruvellier/little_monkey/issues/58)
- Correction du bug [#71](https://github.com/jmcruvellier/little_monkey/issues/71)

## 1.0.1

- Correction du bug [#67](https://github.com/jmcruvellier/little_monkey/issues/67)
- Correction du bug [#68](https://github.com/jmcruvellier/little_monkey/issues/68)

## 1.0.0

- Pays HACS, par @jmcruvellier dans https://github.com/jmcruvellier/little_monkey/pull/66
- Prêt pour la publication dans le Home Assistant Community Store https://github.com/hacs/default/pull/2162

## 0.1.3

- Correction du bug [#63](https://github.com/jmcruvellier/little_monkey/issues/63)

## 0.1.2

- Correction du bug [#63](https://github.com/jmcruvellier/little_monkey/issues/63)

## 0.1.1

- Correction du bug [#59](https://github.com/jmcruvellier/little_monkey/issues/59)

## 0.1.0

- Version Beta

## 0.0.1

- Version Alpha
