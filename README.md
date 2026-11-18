[![CodeQL](https://github.com/jmcruvellier/little_monkey/actions/workflows/github-code-scanning/codeql/badge.svg)](https://github.com/jmcruvellier/little_monkey/actions/workflows/github-code-scanning/codeql)
[![Validate](https://github.com/jmcruvellier/little_monkey/actions/workflows/validate.yml/badge.svg)](https://github.com/jmcruvellier/little_monkey/actions/workflows/validate.yml)
[![Tests](https://github.com/jmcruvellier/little_monkey/actions/workflows/tests.yml/badge.svg)](https://github.com/jmcruvellier/little_monkey/actions/workflows/tests.yml)

![](/custom_components/little_monkey/res/logo_small.png)
# Little Monkey / Petit Singe

Cette intégration permet de récupérer les informations collectées par l'assistant d'énergie ecojoko<sup>©️</sup>.

Elle intègre dans Home Assistant les capteurs suivants:

| Version | Capteur | Type | Unité | Disponibilité | Commentaire |
| ------- | ------- | ---- | ----- | ------------- | ----------- |
| 1.0.0 | Consommation Temps Réel | Puissance | W | Permanent | |
| 1.2.8 | Puissance Apparente | Puissance apparente | VA | Automatique | Créé si ecojoko fournit cette mesure, lue sur le compteur Linky |
| 1.0.0 | Consommation Réseau | Energie | kWh | Permanent | |
| 1.0.0 | Consommation HC Réseau | Energie | kWh | Optionnel | Si vous avez un contrat d'énergie incluant les HC/HP |
| 1.0.0 | Consommation HP Réseau | Energie | kWh | Optionnel | Si vous avez un contrat d'énergie incluant les HC/HP |
| 1.0.0 | Consommation HC/HP Bleu, Blanc, Rouge Réseau | Energie | kWh | Automatique | Une par tranche d'un contrat Tempo |
| 1.3.0 | Consommation d'une tranche tarifaire | Energie | kWh | Automatique | Une par tranche du contrat (Semaine, Week-end, Jour Spécial…), nommée à la configuration |
| 1.3.0 | Période Tarifaire en Cours | Énumération | | Optionnel | Avec les totaux HC/HP ou un contrat Tempo : HC / HP, ou période et couleur Tempo (HC Bleu, HP Rouge...), déduite du compteur qui augmente ; la tranche en cours (Semaine, Week-end, Jour Spécial…) en attribut |
| 1.0.0 | Surplus de Production | Energie | kWh | Optionnel | Si vous êtes producteur d'énergie grâce à des panneaux photovoltaïques et possesseur d'un capteur ecojoko ancienne génération |
| 1.3.0 | Économies sur 7 Jours | Pourcentage | % | Permanent | Écart de la consommation des 7 derniers jours par rapport à votre consommation de référence, négatif pour une économie ; inconnu tant qu'ecojoko n'a pas de semaine de référence. Consommation de référence en attribut |
| 1.3.0 | Consommation sur 7 Jours | Energie | kWh | Permanent | Consommation des 7 derniers jours ; celle de chaque jour, du plus ancien au plus récent, en attribut |
| 1.3.0 | Coût sur 7 Jours | Monétaire | EUR | Permanent | Coût des 7 derniers jours, selon le tarif renseigné dans ecojoko |
| 1.3.0 | Économies Cumulées | Monétaire | EUR | Permanent | Économies depuis le début, négatives en cas de surconsommation |
| 1.3.0 | Puissance Max du Mois | Puissance | W | Permanent | |
| 1.3.0 | Puissance Max de l'Année | Puissance | W | Permanent | |
| 1.3.0 | Puissance Max Depuis le Début | Puissance | W | Permanent | |
| 1.3.0 | Contrat | Texte | | Permanent (diagnostic) | Nom de l'offre lue chez ecojoko ; en attribut, le fournisseur, le type d'offre, la puissance souscrite (kVA), l'abonnement mensuel, la date de début, les plages d'heures creuses et les tranches tarifaires configurées |
| 1.3.0 | Coût de la Consommation sur 12 Mois | Monétaire | EUR | Permanent | Coût de la consommation des 12 derniers mois (« Conso en cours » du résumé des économies d'ecojoko) ; consommation en kWh en attribut |
| 1.3.0 | Coût de Référence sur 12 Mois | Monétaire | EUR | Permanent | Coût de votre consommation de référence sur 12 mois ; consommation de référence en kWh en attribut |
| 1.3.0 | Économies sur 12 Mois | Monétaire | EUR | Permanent | Différence entre les deux, négative en cas de surconsommation ; économies en kWh et niveau (1 à 5) en attribut |
| 1.3.0 | Économies de la Semaine | Monétaire | EUR | Permanent | Économies de la semaine en cours (du lundi au dimanche), négatives en cas de surconsommation ; en attribut, les économies en kWh, les coûts et consommations réels et de référence, et le détail de chaque jour (`bars`, non historisé) |
| 1.3.0 | Économies du Mois | Monétaire | EUR | Permanent | Idem pour le mois en cours, détaillé par semaine |
| 1.3.0 | Économies de l'Année | Monétaire | EUR | Permanent | Idem pour l'année en cours, détaillée par mois |
| 1.3.0 | Mode (équipement piloté) | Énumération | | Automatique | Un par équipement piloté par ecojoko (chauffe-eau, prise…), sur l'appareil de l'équipement : Automatique, Forcé ou Absence (Allumé ou Éteint pour un équipement sans mode forcé) ; en attribut, l'état du contacteur tel qu'ecojoko l'écrit, depuis et jusqu'à quand, et l'origine du changement (commande, programmation, fin de durée) |
| 1.3.0 | Pilotage (équipement piloté) | Liste | | Automatique | Pilote l'équipement comme l'application ecojoko : Automatique, Forcé (pendant une heure) ou Absence (jusqu'à minuit) ; Allumé ou Éteint pour un équipement sans mode forcé. Le service « Piloter un équipement » choisit n'importe quelle durée |
| 1.3.0 | Puissance (équipement piloté) | Puissance | W | Automatique | Puissance consommée par l'équipement |
| 1.3.0 | Consommation du Jour (équipement piloté) | Energie | kWh | Automatique | Énergie consommée par l'équipement depuis minuit, s'il mesure sa consommation |
| 1.3.0 | Coût du Jour (équipement piloté) | Monétaire | EUR | Automatique | Coût de cette énergie, selon le tarif renseigné dans ecojoko |
| 1.3.0 | Connexion à l'Assistant, Force de la Connexion, Connexion au WiFi, Batterie (équipement) | Diagnostic | %  | Automatique | Pour chaque équipement de l'installation, quand ecojoko donne la valeur : sur l'appareil d'un équipement piloté (chauffe-eau…), sur l'appareil Little Monkey pour les autres (« Clé Linky : force de la connexion », « Sonde de température : connexion à l'assistant »…) |
| 1.0.0 | Température Intérieure | Température | °C | Optionnel | |
| 1.0.0 | Température Extérieure | Température | °C | Optionnel | |
| 1.0.0 | Humidité Intérieure | Humidité | % | Optionnel | |
| 1.0.0 | Humidité Extérieure | Humidité | % | Optionnel | |

Elle fournit aussi une carte « Little Monkey » pour vos tableaux de bord, chargée automatiquement : voir [la configuration de la carte](https://github.com/jmcruvellier/little_monkey/blob/main/CONFIGURATION.md#carte-du-tableau-de-bord). Les cartes des économies reprennent l'onglet « Économies » d'ecojoko : voir [leur configuration](https://github.com/jmcruvellier/little_monkey/blob/main/CONFIGURATION.md#cartes-des-%C3%A9conomies). La carte des équipements reprend l'écran « Équipements » et pilote le chauffe-eau : voir [sa configuration](https://github.com/jmcruvellier/little_monkey/blob/main/CONFIGURATION.md#carte-des-%C3%A9quipements).

> [!IMPORTANT]
> Si vous êtes un utilisateur régulier de l'application ecojoko<sup>©️</sup>, vous n'êtes pas sans savoir que le petit singe glisse souvent sur sa peau de banane. **Cette __intégration non-officielle__ dépend des APIs d'ecojoko<sup>©️</sup> et n'est donc pas responsable en cas d'indisponibilité de vos données.**

Bienvenue dans la jungle!

## Pourquoi avoir développé cette intégration?

Les données de votre compteur sont stockées sur les serveurs d'ecojoko<sup>©️</sup>. C'est de là que l'application mobile ou le site web d'[ecojoko<sup>©️</sup>](https://service.ecojoko.com/) chargent les informations que vous consultez.
Jusque là tout va bien, on peut suivre sa consommation en temps réel, ce qui est la première étape quand on cherche à optimiser/réduire de sa consommation énergétique.
Dans le monde de la domotique on souhaite aller plus loin, comme par exemple:

* recevoir des alertes en fonction de seuils de consommation ou de production
* lancer des automatisations
* et beaucoup d'autres choses

Ecojoko<sup>©️</sup> ne proposant pas d'intégration officielle pour Home Assistant, je me suis donc lancé dans le développement de celle-ci.

## Prérequis

Avant de vous lancer dans l'installation, il est nécessaire:

1. d'être en possession d'un capteur ecojoko<sup>©️</sup>
1. de connaitre ses identifiants de connexion au site d'[ecojoko<sup>©️</sup>](https://service.ecojoko.com/)

## Installation & configuration

### Ajouter le dépôt de l'intégration dans Home Assistant avec HACS

Cliquer sur le lien ci-dessous pour ajouter le dépôt de l'intégration:

[![Ouvre votre instance Home Assistant et ajoute un dépôt dans la boutique communautaire Home Assistant.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=jmcruvellier&repository=little_monkey&category=integration)

### Installation & Configuration de l'intégration

Suivre les [instructions d'installation et de configuration](https://github.com/jmcruvellier/little_monkey/blob/main/CONFIGURATION.md)

## Liens utiles
Pour les possesseurs:
* d'un contrat d'énergie Tempo
  - l'intégration d'Edouard Hur qui permet d'avoir le calendrier des jours Tempo ainsi que des capteurs très utiles [RTE Tempo](https://github.com/hekmon/rtetempo)
* de panneaux photovoltaïques, Mathieu Carbou propose :
  - un boitier [OpenDTU](https://docs.google.com/document/u/0/d/e/2PACX-1vRaGy2E91kmr014nAi-rfvNxdpZqR6lFIXln1kMKg_T6_YWh72ZNLnwXHxUjQQexczNPZR3GftG7w-r/pub?pli=1) clé en main déjà prêt pour être connecté aux micro-onduleurs de vos panneaux
  - des [Cartes pour Home Assistant](https://gist.github.com/mathieucarbou/70539ced8f330be6205a91897ea1c639#opendtu--home-assistant) afin de rendre plus facile le suivi de production de vos panneaux dans les tableaux de bord
