# -*- coding:utf-8 -*-

token = open("resources/token.tk", 'r', encoding='UTF8')
tokenf = token.read()
token.close()


def getToken():
    return tokenf


def setToken(tk):
    tokenf = tk
