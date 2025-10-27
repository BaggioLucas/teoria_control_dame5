#include "beremiz.h"
#ifndef __POUS_H
#define __POUS_H

#include "accessor.h"
#include "iec_std_lib.h"

__DECLARE_ENUMERATED_TYPE(LOGLEVEL,
  LOGLEVEL__CRITICAL,
  LOGLEVEL__WARNING,
  LOGLEVEL__INFO,
  LOGLEVEL__DEBUG
)
// FUNCTION_BLOCK LOGGER
// Data part
typedef struct {
  // FB Interface - IN, OUT, IN_OUT variables
  __DECLARE_VAR(BOOL,EN)
  __DECLARE_VAR(BOOL,ENO)
  __DECLARE_VAR(BOOL,TRIG)
  __DECLARE_VAR(STRING,MSG)
  __DECLARE_VAR(LOGLEVEL,LEVEL)

  // FB private variables - TEMP, private and located variables
  __DECLARE_VAR(BOOL,TRIG0)

} LOGGER;

void LOGGER_init__(LOGGER *data__, BOOL retain);
// Code part
void LOGGER_body__(LOGGER *data__);
// PROGRAM PROGRAM0
// Data part
typedef struct {
  // PROGRAM Interface - IN, OUT, IN_OUT variables

  // PROGRAM private variables - TEMP, private and located variables
  __DECLARE_LOCATED(BOOL,OUTB)
  __DECLARE_LOCATED(BOOL,INPUT1)
  __DECLARE_LOCATED(BOOL,OUTA)
  __DECLARE_LOCATED(BOOL,OUTF)
  __DECLARE_LOCATED(BOOL,OUTG)
  __DECLARE_LOCATED(BOOL,OUTC)
  __DECLARE_LOCATED(BOOL,OUTD)
  __DECLARE_LOCATED(BOOL,OUTE)
  __DECLARE_VAR(BOOL,TRU)
  TP TP0;
  TOF TOF0;
  TP TP1;
  TP TP2;
  __DECLARE_VAR(BOOL,_TMP_NOT17_OUT)
  __DECLARE_VAR(BOOL,_TMP_AND15_OUT)
  __DECLARE_VAR(BOOL,_TMP_AND16_OUT)
  __DECLARE_VAR(BOOL,_TMP_NOT22_OUT)
  __DECLARE_VAR(BOOL,_TMP_AND26_OUT)
  __DECLARE_VAR(BOOL,_TMP_OR27_OUT)
  __DECLARE_VAR(BOOL,_TMP_OR20_OUT)

} PROGRAM0;

void PROGRAM0_init__(PROGRAM0 *data__, BOOL retain);
// Code part
void PROGRAM0_body__(PROGRAM0 *data__);
#endif //__POUS_H
