import time
import random

import numpy as np
from numba import njit
import pygame
import math


##########################################################################
#
#  Color
#
##########################################################################


class Color:
    pink   = (255, 105, 180)
    orange = (255, 165, 0)
    cyan   = (0, 255, 255)
    red    = (255, 0, 0)
    yellow = (255, 255, 0)
    blue   = (0, 0, 255)
    white  = (255, 255, 255)
    black  = (0, 0, 0)
    gray   = (128,128,128)



##########################################################################
#
#  Etat du jeu
#
##########################################################################


class GameData:
    # index 0 = rester sur place

    def __init__(self, map_text):
        self.map, self.mapW, self.mapH = self._mapCreate(map_text)

        self.walkable = self._buildWalkableMask()

        self.stands = self._findStands()

        self.spawns = self._getSpawns()

        self.checkouts = self._getCheckouts()


    ######################################################################
    # map
    ######################################################################

    def _mapCreate(self, text):
        rows = text.strip().splitlines()
        rows = [line.strip() for line in rows]
        rows = [line.replace(".", "") for line in rows]

        for line in rows:
            if len(line) != len(rows[0]):
                print("different length :", line)
                raise Exception("Map length error")

        rows.reverse()  # met l'origine en bas a gauche
        grid = [[ c for c in row] for row in rows]

        array = np.array(grid, dtype='U1').transpose()
        width, height = array.shape
        return array, width, height



    def _findStands(self):
        stands = []

        for x in range(self.mapW):
            for y in range(self.mapH):
                cell = self.map[x, y]

                if cell in ('F') :
                    stands.append((x, y))

        return stands

    def _getSpawns(self):
        spawns = []

        for x in range(self.mapW):
            for y in range(self.mapH):
                if self.map[x, y] == 'W':
                    spawns.append((x, y))

        return spawns

    def _getCheckouts(self):
        checkouts = []

        for x in range(self.mapW):
            for y in range(self.mapH):
                if self.map[x, y] == 'S':
                    checkouts.append((x, y))

        return checkouts

    def _buildWalkableMask(self):
        """Masque booleeen numpy des cases praticables (utilisable par Numba)."""
        walkable_chars = {' ', 'W', 'S'}
        mask = np.zeros((self.mapW, self.mapH), dtype=np.bool_)
        for x in range(self.mapW):
            for y in range(self.mapH):
                mask[x, y] = self.map[x, y] in walkable_chars
        return mask


#######################################
#
#  Screen control
#
##########################################################################

ZOOM = 40
SPEED = 2   # cases par seconde


class Screen:
    def __init__(self, nx, ny, title="ESIEE - Supermarket Simulator"):

        self.SCREEN_WIDTH  = nx   * ZOOM
        self.SCREEN_HEIGHT = (ny + 1) * ZOOM
        self.EPAISS = 8

        pygame.display.init()
        pygame.font.init()
        self.screen = pygame.display.set_mode((self.SCREEN_WIDTH, self.SCREEN_HEIGHT))
        pygame.display.set_caption(title)
        self.clock = pygame.time.Clock()

        self.font22 = pygame.font.SysFont("Arial", 24, bold=True)
        self.font_debug = pygame.font.SysFont("Arial", 16)

    ######################################################################
    # conversions coordonnees
    ######################################################################

    def screen_to_grid(self, xpix, ypix):
        xpix += ZOOM // 2
        gx = xpix // ZOOM - 1
        ypix -= ZOOM // 2
        gy = (self.SCREEN_HEIGHT - ypix) // ZOOM - 2
        return gx, gy

    def grid_to_screen(self, x, y):
        sx = (x ) * ZOOM
        sy = self.SCREEN_HEIGHT - (y + 1) * ZOOM
        return sx, sy

    ######################################################################
    # primitives de dessin
    ######################################################################

    def clear(self,coul=Color.black):
        self.screen.fill(coul)

    def drawRect(self,x,y,L,H,coul,width = 0):
        x1, y1 = self.grid_to_screen(x, y)
        HH = ZOOM * H
        LL = ZOOM * L
        pygame.draw.rect(self.screen, coul, (x1, y1-HH, LL, HH),width = width)


    def drawCircle(self, x, y, r, color = Color.red):
        R = r*ZOOM
        cx, cy = self.grid_to_screen(x , y )
        pygame.draw.circle(self.screen, color, (cx, cy) , R)


    def drawText(self, x, y, txt, color=Color.white, bigfont=False, centered=False):
        font = self.font22 if bigfont else self.font_debug
        xx, yy = self.grid_to_screen(x, y)
        text_surface = font.render(str(txt), True, color)
        height = text_surface.get_height()
        width  = text_surface.get_width()

        if (centered):
            self.screen.blit(text_surface, (xx-width//2, yy - height//2))
        else:
            self.screen.blit(text_surface, (xx, yy - height))

    def drawTriangle(self, A,B,C, color=Color.orange):
        p1 = self.grid_to_screen(*A)
        p2 = self.grid_to_screen(*B)
        p3 = self.grid_to_screen(*C)

        pygame.draw.polygon(self.screen,color,
            [
                (int(p1[0]), int(p1[1])),
                (int(p2[0]), int(p2[1])),
                (int(p3[0]), int(p3[1])),
            ],
        )

    def debugDist(self, dist):
        for x in range(G.mapW):
            for y in range(G.mapH):
                if G.map[x,y] == ' ':
                    v = dist[x,y]
                    self.drawText(x+0.5,y+0.5,str(v),Color.white,False,True)


    def buildBackground(self):
        """Dessine le decor statique une seule fois dans un buffer."""
        self.background = pygame.Surface((self.SCREEN_WIDTH, self.SCREEN_HEIGHT))
        self.background.fill(Color.black)
        for x in range(G.mapW):
            for y in range(G.mapH):
                cell = G.map[x, y]
                if cell != ' ':
                    coul = TableCoul[cell]
                    x1, y1 = self.grid_to_screen(x, y)
                    pygame.draw.rect(self.background, coul,        (x1, y1 - ZOOM, ZOOM, ZOOM))
                    pygame.draw.rect(self.background, Color.black, (x1, y1 - ZOOM, ZOOM, ZOOM), 2)

    def blitBackground(self):
        """Copie le buffer de decor sur l'ecran (remplace clear + double boucle)."""
        self.screen.blit(self.background, (0, 0))

    def show(self):
        pygame.display.flip()





##########################################################################
#
#  PROJET
#
##########################################################################


T = """
.M.M.M.M.M.M.M.M.M.M.M.M.M.M.M.M.M.M.M.M.M.M.M.M.M.M.M.M.M.M
.M.M.M.M.M.M.M.M.M.M.M.M.M.U. .U. .U. .U. . .O.O.O.O.O.O.O.M
.M.M.M.M.M.M.M.M.M.M.M.M.M.U. .U. .U. .U. . . . . . . . . .M
.M.B.B.B.B.B. .A.A.A.A.A.A.A. . . . . . . . .O.O.O.M.O.O. .M
.M.B. . . . . . . . . . . . . . . . . . . . . . . . . . . .M
.M.B. .B.B.B. .A.A.A.A.A.A.A. .U. .U. .J. . .O.O.O.O.O.O. .M
.M.B. .B.B.B. .A.M.M.M.M.M.A. .U. .U. .J. . .J.J.J.J.J.J. .M
.M.L. . . . . . . . . . . . . . . . . . . . . . . . . . . .M
.M.L. .L.L.L.L. .F. .F. .T.T. .T.T. .P.P. . .J.J.J.M.J.J. .M
.M.L. . . . . . .F. .F. .T.T. .T.T. .P.P. . .J.J.J.J.J.J. .M
.M.L. .L.L.M.L. .F. .F. .M.T. .T.T. .M.P. . . . . . . . . .M
.M.L. . . . . . .F. .F. .T.T. .T.T. .P.P. . .J.J.J.J.J.J. .M
.M.L. .L.L.L.L. .F. .F. .T.T. .T.T. .P.P. . .J.J.J.J.J.J. .M
.M.L. . . . . . . . . . . . . . . . . . . . . . . . . . . .M
.M.L. . . . . . . . . . . . . . . . . . . . . . . . . . .R.M
.M.G. .G.G. .G.E. .E.E. .E.E. .E.E. .P. . . .R.R. .M.R. .R.M
.M.G. . . . .G.E. .E.E. .E.E. .E.E. .P. . . . . . . . . .R.M
.M.G. .G.G. .G.E. .E.E. .M.E. .E.E. .P. . . .R.R. .R.R. .R.M
.M.G. .G.G. .G.E. .E.E. .E.E. .E.E. .P. . . . . . . . . .R.M
.M.G. .G.G. .G.E. .E.E. .E.E. .E.E. .P. . . .R.R. .R.R. .R.M
.M.G. . . . . . . . . . . . . . . . . . . . . . . . . . .R.M
.M.M.M.M.M.S.M.M.S.M.M.S.M.M.S.M.M.S.M.W.W.W.M.M.M.M.M.M.M.M
"""

TableCoul = {
'G' : (132, 211, 245), #surGelés
'M' : (133, 152, 167), #mur
'B' : (235, 52, 36)  , #boucherie
'L' : (146, 186, 61) , #légumes
'E' : (173, 115, 93) , #Epicerie
'F' : (159, 117, 195), #fruits
'A' : (172, 36, 74)  , #Alcool/Vin
'T' : (255, 210, 227), #textile
'P' : (254, 255, 55) , #promotions
'J' : (252, 147, 30) , #jouets
'R' : (255, 223, 148), #électRonique
'S' : (220, 220, 220), #Sorties
'O' : (14, 147, 255) , #bOissons
'U' : (171, 45, 144) , #sUcrée
'W' : (40,40,40)          #spawn
}


class Customer:
    def __init__(self, game):
        spawns = game.spawns
        if not spawns:
            raise ValueError("No spawn found on the map")
        if not game.checkouts:
            raise ValueError("No checkout found on the map")

        self.STATE_SHOPPING = "faire_les_courses"
        self.STATE_GO_CHECKOUT = "aller_aux_caisses"
        self.STATE_CHECKOUT = "passage_en_caisse"

        self.x, self.y = spawns[0]
        self.x += 0.5 # on demarre au milieu de la case
        self.y += 0.5
        nb_targets     = 10
        self.targets   = random.sample(game.stands, nb_targets)
        self.dir       = (0,1)
        self.current_target = None
        self.arrival_threshold = 1
        self.state = self.STATE_SHOPPING
        self.checkout_start_time = None
        self.visible = True
        self.dist = np.empty((G.mapW, G.mapH), dtype=np.int32)

        self._selectNearestTarget()

    def _selectNearestTarget(self):
        """Selectionne le target le plus proche et calcule sa carte de distances."""
        if not self.targets:
            self.current_target = None
            return

        cx, cy = int(self.x), int(self.y)
        best_target = None
        best_dist = float('inf')

        for target in self.targets:
            computeDist(self.dist, *target)
            d = self.dist[cx, cy]
            if d < best_dist:
                best_dist = d
                best_target = target

        self.current_target = best_target
        if best_target:
            computeDist(self.dist, *best_target)
            self.arrival_threshold = 1

    def _selectNearestCheckout(self):
        """Selectionne la caisse la plus proche depuis la position courante."""
        cx, cy = int(self.x), int(self.y)
        best_checkout = None
        best_dist = float('inf')

        for checkout in G.checkouts:
            computeDist(self.dist, *checkout)
            d = self.dist[cx, cy]
            if d < best_dist:
                best_dist = d
                best_checkout = checkout

        self.current_target = best_checkout
        if best_checkout:
            computeDist(self.dist, *best_checkout)
            self.arrival_threshold = 0

    def move(self, dt):
        if not self.visible:
            return

        if self.state == self.STATE_CHECKOUT:
            if self.checkout_start_time is not None and time.time() - self.checkout_start_time >= 10.0:
                self.visible = False
            return

        if self.state == self.STATE_SHOPPING and not self.targets:
            self.state = self.STATE_GO_CHECKOUT
            self._selectNearestCheckout()

        ix = int(self.x)
        iy = int(self.y)

        if self.dist[ix, iy] <= self.arrival_threshold:
            if self.state == self.STATE_SHOPPING:
                # Arrive au target courant : le retirer et choisir le suivant
                if self.current_target in self.targets:
                    self.targets.remove(self.current_target)

                if self.targets:
                    self._selectNearestTarget()
                else:
                    self.state = self.STATE_GO_CHECKOUT
                    self._selectNearestCheckout()
            elif self.state == self.STATE_GO_CHECKOUT:
                self.state = self.STATE_CHECKOUT
                self.checkout_start_time = time.time()
                self.dir = (0, 0)
            return

        # Trouver parmi les 4 voisins celui avec la distance minimale
        best_dir = None
        best_dist = self.dist[ix, iy]
        for ddx, ddy in [(-1,0),(1,0),(0,-1),(0,1)]:
            nx, ny = ix + ddx, iy + ddy
            if 0 <= nx < G.mapW and 0 <= ny < G.mapH:
                d = self.dist[nx, ny]
                if d < best_dist:
                    best_dist = d
                    best_dir = (ddx, ddy)

        if best_dir is not None:
            self.dir = best_dir
            self.x += best_dir[0] * SPEED * dt
            self.y += best_dir[1] * SPEED * dt
            # Recentre l'axe perpendiculaire au mouvement dans sa case
            if best_dir[0] != 0:   # deplacement horizontal => snap y
                self.y = int(self.y) + 0.5
            else:                  # deplacement vertical   => snap x
                self.x = int(self.x) + 0.5

    def drawCustomer(self):
        if not self.visible:
            return

        x,y = self.x, self.y
        dx, dy = self.dir
        norm = math.hypot(dx, dy)
        if ( norm > 0.001) :
            dx = dx / norm
            dy = dy / norm
            lx,ly = -dy,dx # rot90
            l = 0.5  # longueur de la fleche
            s = 0.15  # largeur
            A = x + l * dx , y + l * dy
            B = x + s * lx , y + s * ly
            C = x - s * lx , y - s * ly
            S.drawTriangle(A,B,C,Color.white)

    def drawTargets(self):
        if not self.visible:
            return

        for x, y in self.targets:
            S.drawCircle(x+0.5,y+0.5,0.1,Color.white)


@njit(cache=True)
def computeDistJit(dist, walkable, tx, ty, mapW, mapH):
    """Version compilee Numba : tableaux numpy et valeurs numeriques uniquement."""
    for x in range(mapW):
        for y in range(mapH):
            if x == tx and y == ty:
                dist[x, y] = 0
            elif walkable[x, y]:
                dist[x, y] = 100
            else:
                dist[x, y] = 999

    changed = True
    while changed:
        changed = False
        for x in range(mapW):
            for y in range(mapH):
                if walkable[x, y]:
                    best = 999
                    if x > 0 and dist[x-1, y] < best:
                        best = dist[x-1, y]
                    if x < mapW - 1 and dist[x+1, y] < best:
                        best = dist[x+1, y]
                    if y > 0 and dist[x, y-1] < best:
                        best = dist[x, y-1]
                    if y < mapH - 1 and dist[x, y+1] < best:
                        best = dist[x, y+1]
                    new_val = best + 1
                    if new_val < dist[x, y]:
                        dist[x, y] = new_val
                        changed = True


def computeDist(dist, tx, ty):
    """Calcule la carte des distances vers (tx, ty) dans le tableau dist fourni."""
    computeDistJit(dist, G.walkable, tx, ty, G.mapW, G.mapH)


G = GameData(T)
S = Screen(G.mapW, G.mapH)
CUST = Customer(G)
S.buildBackground()





def drawMap():
    S.blitBackground()

    CUST.drawCustomer()


    S.drawText(0,-1, "  SPACE = pause", color=Color.white, bigfont=True)

    S.debugDist(CUST.dist)

    S.show()


def playOneTurn(dt):
    if not PAUSE_FLAG:
        CUST.move(dt)


##########################################################################
#
#  Boucle principale
#
##########################################################################

PAUSE_FLAG = False
LOGIC_CALL = pygame.USEREVENT + 1
LOGIC_fps = 10
pygame.time.set_timer(LOGIC_CALL, int(1000 / LOGIC_fps))

running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
            PAUSE_FLAG = not PAUSE_FLAG
        elif event.type == LOGIC_CALL:
            playOneTurn(1 / LOGIC_fps)

    drawMap()
    S.clock.tick(60)

pygame.quit()
