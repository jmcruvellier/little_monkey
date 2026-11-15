# Changelog

## 1.2.8
- Correction des données de consommation erronées (Consommation Réseau, HC/HP, Tempo, surplus de production) : l'API ecojoko renvoyait des valeurs dégradées au User-Agent par défaut de Home Assistant, l'intégration envoie désormais son propre User-Agent
- Les capteurs passent à l'état « indisponible » quand l'API ecojoko ne répond plus, au lieu de rester figés sur leur dernière valeur ; les erreurs sont désormais journalisées
- Température et humidité : rafraîchissement désormais assuré quelle que soit la fréquence choisie (elles n'étaient plus mises à jour à partir de 15 secondes pour l'humidité et de 30 secondes pour la température), et plus aucun appel à ces APIs quand l'option est décochée
- Les données de consommation ne sont plus figées pendant une heure lors du passage à l'heure d'hiver
- Suppression de deux dépendances non déclarées (`async_timeout`, `pytz`) au profit de la bibliothèque standard de Python

## 1.2.7
- Correction du bug [#118](https://github.com/jmcruvellier/little_monkey/issues/118) : Entités non affichées dans l'appareil Ecojoko

## 1.2.6
- Correction du bug [#116](https://github.com/jmcruvellier/little_monkey/issues/116) : Problème de reporting sur la page energie

## 1.2.5
- Correction du bug [#110](https://github.com/jmcruvellier/little_monkey/issues/110) : Surplus de production attendu en positif et plus en négatif
- Fix URL dans le json des traductions (nouvelle règle de validation de la qualité du code)

## 1.2.4
- Bug fix [#101](https://github.com/jmcruvellier/little_monkey/issues/101)

## 1.2.3
- Bug fix [#93](https://github.com/jmcruvellier/little_monkey/issues/93)
- Addition of Portuguese to the list of available languages [#80](https://github.com/jmcruvellier/little_monkey/pull/80) [#88](https://github.com/jmcruvellier/little_monkey/pull/88) [#89](https://github.com/jmcruvellier/little_monkey/pull/89)

## 1.2.2
- Bug fix [#74](https://github.com/jmcruvellier/little_monkey/issues/74)

## 1.2.1
- Bug fix [#78](https://github.com/jmcruvellier/little_monkey/issues/78)

## 1.2.0
- Major code and performance optimization
- Removed sensors introduced in v1.1.0 based on ecojoko Measurements APIs
- Bug fix [#58](https://github.com/jmcruvellier/little_monkey/issues/58)

## 1.1.0
- New sensors based on ecojoko Measurements APIs
- Some performance improvement and minor bug fixes
- Bug fix [#58](https://github.com/jmcruvellier/little_monkey/issues/58)
- Bug fix [#71](https://github.com/jmcruvellier/little_monkey/issues/71)

## 1.0.1

- Bug fix [#67](https://github.com/jmcruvellier/little_monkey/issues/67)
- Bug fix [#68](https://github.com/jmcruvellier/little_monkey/issues/68)

## 1.0.0

- HACS country by @jmcruvellier in https://github.com/jmcruvellier/little_monkey/pull/66
- Ready for publication in Home Assistant Community Store https://github.com/hacs/default/pull/2162

## 0.1.3

- Bug fix [#63](https://github.com/jmcruvellier/little_monkey/issues/63)

## 0.1.2

- Bug fix [#63](https://github.com/jmcruvellier/little_monkey/issues/63)

## 0.1.1

- Bug fix [#59](https://github.com/jmcruvellier/little_monkey/issues/59)

## 0.1.0

- Version Beta

## 0.0.1

- Version Alpha
