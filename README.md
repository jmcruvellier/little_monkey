# ![Little Monkey](/custom_components/little_monkey/res/logo.png)

Cette intégration vous permet de récupérer les informations collectées par votre capteur ecojoko.

Elle permet d'intègrer dans Home Assistant les capteurs suivants:

* Consommation Temps Réel
* Consommation Réseau
* Consommation HC Réseau
* Consommation HP Réseau
* Consommation HC Bleu Réseau
* Consommation HP Bleu Réseau
* Consommation HC Blanc Réseau
* Consommation HP Blanc Réseau
* Consommation HC Rouge Réseau
* Consommation HP Rouge Réseau
* Surplus de Production
* Température Intérieure
* Température Extérieure
* Humidité Intérieure
* Humidité Extérieure

## Pourquoi avoir voulu développer cette intégration?

Les données de votre capteur installé sur votre compteur sont stockées sur les serveurs d'ecojoko. C'est de là que l'application mobile ou le site d'[ecojoko](https://service.ecojoko.com/) chargent les informations que vous consultez.
Jusque là tout va bien, on peut suivre sa consommation en temps réel, ce qui est la première étape quand on veut optimiser/réduire de sa consommation énergétique.
Mais là où sa coince c'est lorsque l'on souhaite aller plus loin, comme par exemple:

* recevoir des alertes en fonction de seuils de consommation ou de production
* lancer des automatisations
* et beaucoup d'autres choses que nous permettent de faire les outils domotiques

Ecojoko ne proposant pas d'intégration officielle pour Home Assistant, je me suis donc lancé dans le développement de celle-ci.

## Prérequis

1. Etre en possession d'un capteur ecojoko
1. Connaitre ses identifiants de connexion au site d'[ecojoko](https://service.ecojoko.com/)

## Installation de l'intégration dans Home Assistant avec HACS

[![Ouvre votre instance Home Assistant et ajoute un dépôt dans la boutique communautaire Home Assistant.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=jmcruvellier&repository=little_monkey&category=integration)

Une fois l'intégration téléchargée, redémarrez votre Home Assistant.

## Configuration de l'intégration

TODO (capture)

## Liens utiles
Pour les possesseurs:
* d'un contrant d'énergie Tempo
  - l'intégration d'Edouard Hur @hekmon qui permet d'avoir le calendrier des jours Tempo ainsi que des capteurs très utiles [RTE Tempo](https://github.com/hekmon/rtetempo)
* de panneaux photovoltaiques, Mathieu Carbou @mathieucarbou propose :
  - un boitier [OpenDTU](https://docs.google.com/document/u/0/d/e/2PACX-1vRaGy2E91kmr014nAi-rfvNxdpZqR6lFIXln1kMKg_T6_YWh72ZNLnwXHxUjQQexczNPZR3GftG7w-r/pub?pli=1) clé en main déjà prêt pour être connecté aux micro-onduleurs de vos panneaux
  - des [Cartes pour Home Assistant](https://gist.github.com/mathieucarbou/70539ced8f330be6205a91897ea1c639#opendtu--home-assistant) afin de rendre plus facile le suivi de production de vos panneaux dans les tableaux de bord
