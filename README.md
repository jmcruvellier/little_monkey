![](/custom_components/little_monkey/res/logo_small.png)
# Little Monkey / Petit Singe

Cette intégration vous permet de récupérer les informations collectées par votre installation ecojoko<sup>©️</sup>.

Elle intègre dans Home Assistant les capteurs suivants:

* Consommation Temps Réel (Puissance en W)
* Consommation Réseau (Energie en kWh)
* Si vous avez un contrat d'énergie HC/HP
  - Consommation HC Réseau (Energie en kWh)
  - Consommation HP Réseau (Energie en kWh)
  - Si c'est un contrat Tempo:
    - Consommation HC Bleu Réseau (Energie en kWh)
    - Consommation HP Bleu Réseau (Energie en kWh)
    - Consommation HC Blanc Réseau (Energie en kWh)
    - Consommation HP Blanc Réseau (Energie en kWh)
    - Consommation HC Rouge Réseau (Energie en kWh)
    - Consommation HP Rouge Réseau (Energie en kWh)
* Si vous êtes producteur d'énergie grâce à des panneaux photovoltaïques et possesseur d'un capteur ecojoko ancienne génération:
  - Surplus de Production (Energie en kWh)
* Température Intérieure (en °C)
* Température Extérieure (en °C)
* Humidité Intérieure (en %)
* Humidité Extérieure (en %)

> [!IMPORTANT]
> Si vous êtes un utilisateur régulier de l'application ecojoko<sup>©️</sup>, vous n'êtes pas sans savoir que le petit singe glisse souvent sur sa peau de banane. **Cette __intégration non-officielle__ dépend des APIs d'ecojoko<sup>©️</sup> et n'est donc pas responsable en cas d'indisponibilité de vos donnés.**

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

Suivre les [instructions d'installation et de configuration](CONFIGURATION.md)

## Liens utiles
Pour les possesseurs:
* d'un contrant d'énergie Tempo
  - l'intégration d'Edouard Hur qui permet d'avoir le calendrier des jours Tempo ainsi que des capteurs très utiles [RTE Tempo](https://github.com/hekmon/rtetempo)
* de panneaux photovoltaiques, Mathieu Carbou propose :
  - un boitier [OpenDTU](https://docs.google.com/document/u/0/d/e/2PACX-1vRaGy2E91kmr014nAi-rfvNxdpZqR6lFIXln1kMKg_T6_YWh72ZNLnwXHxUjQQexczNPZR3GftG7w-r/pub?pli=1) clé en main déjà prêt pour être connecté aux micro-onduleurs de vos panneaux
  - des [Cartes pour Home Assistant](https://gist.github.com/mathieucarbou/70539ced8f330be6205a91897ea1c639#opendtu--home-assistant) afin de rendre plus facile le suivi de production de vos panneaux dans les tableaux de bord
