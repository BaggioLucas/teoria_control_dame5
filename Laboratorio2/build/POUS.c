void LOGGER_init__(LOGGER *data__, BOOL retain) {
  __INIT_VAR(data__->EN,__BOOL_LITERAL(TRUE),retain)
  __INIT_VAR(data__->ENO,__BOOL_LITERAL(TRUE),retain)
  __INIT_VAR(data__->TRIG,__BOOL_LITERAL(FALSE),retain)
  __INIT_VAR(data__->MSG,__STRING_LITERAL(0,""),retain)
  __INIT_VAR(data__->LEVEL,LOGLEVEL__INFO,retain)
  __INIT_VAR(data__->TRIG0,__BOOL_LITERAL(FALSE),retain)
}

// Code part
void LOGGER_body__(LOGGER *data__) {
  // Control execution
  if (!__GET_VAR(data__->EN)) {
    __SET_VAR(data__->,ENO,,__BOOL_LITERAL(FALSE));
    return;
  }
  else {
    __SET_VAR(data__->,ENO,,__BOOL_LITERAL(TRUE));
  }
  // Initialise TEMP variables

  if ((__GET_VAR(data__->TRIG,) && !(__GET_VAR(data__->TRIG0,)))) {
    #define GetFbVar(var,...) __GET_VAR(data__->var,__VA_ARGS__)
    #define SetFbVar(var,val,...) __SET_VAR(data__->,var,__VA_ARGS__,val)

   LogMessage(GetFbVar(LEVEL),(char*)GetFbVar(MSG, .body),GetFbVar(MSG, .len));
  
    #undef GetFbVar
    #undef SetFbVar
;
  };
  __SET_VAR(data__->,TRIG0,,__GET_VAR(data__->TRIG,));

  goto __end;

__end:
  return;
} // LOGGER_body__() 





void PROGRAM0_init__(PROGRAM0 *data__, BOOL retain) {
  __INIT_LOCATED(BOOL,__QX0_0,data__->OUTB,retain)
  __INIT_LOCATED_VALUE(data__->OUTB,0)
  __INIT_LOCATED(BOOL,__IX0_0,data__->INPUT1,retain)
  __INIT_LOCATED_VALUE(data__->INPUT1,0)
  __INIT_LOCATED(BOOL,__QX0_1,data__->OUTA,retain)
  __INIT_LOCATED_VALUE(data__->OUTA,0)
  __INIT_LOCATED(BOOL,__QX0_2,data__->OUTF,retain)
  __INIT_LOCATED_VALUE(data__->OUTF,0)
  __INIT_LOCATED(BOOL,__QX0_3,data__->OUTG,retain)
  __INIT_LOCATED_VALUE(data__->OUTG,0)
  __INIT_LOCATED(BOOL,__QX0_4,data__->OUTC,retain)
  __INIT_LOCATED_VALUE(data__->OUTC,0)
  __INIT_LOCATED(BOOL,__QX0_5,data__->OUTD,retain)
  __INIT_LOCATED_VALUE(data__->OUTD,0)
  __INIT_LOCATED(BOOL,__QX0_6,data__->OUTE,retain)
  __INIT_LOCATED_VALUE(data__->OUTE,0)
  __INIT_VAR(data__->TRU,1,retain)
  TP_init__(&data__->TP0,retain);
  TOF_init__(&data__->TOF0,retain);
  TP_init__(&data__->TP1,retain);
  TP_init__(&data__->TP2,retain);
  __INIT_VAR(data__->_TMP_NOT17_OUT,__BOOL_LITERAL(FALSE),retain)
  __INIT_VAR(data__->_TMP_AND15_OUT,__BOOL_LITERAL(FALSE),retain)
  __INIT_VAR(data__->_TMP_AND16_OUT,__BOOL_LITERAL(FALSE),retain)
  __INIT_VAR(data__->_TMP_NOT22_OUT,__BOOL_LITERAL(FALSE),retain)
  __INIT_VAR(data__->_TMP_AND26_OUT,__BOOL_LITERAL(FALSE),retain)
  __INIT_VAR(data__->_TMP_OR27_OUT,__BOOL_LITERAL(FALSE),retain)
  __INIT_VAR(data__->_TMP_OR20_OUT,__BOOL_LITERAL(FALSE),retain)
}

// Code part
void PROGRAM0_body__(PROGRAM0 *data__) {
  // Initialise TEMP variables

  __SET_VAR(data__->TP0.,IN,,__GET_LOCATED(data__->INPUT1,));
  __SET_VAR(data__->TP0.,PT,,__time_to_timespec(1, 5000, 0, 0, 0, 0));
  TP_body__(&data__->TP0);
  __SET_VAR(data__->,_TMP_NOT17_OUT,,!(__GET_VAR(data__->TP0.Q,)));
  __SET_VAR(data__->,_TMP_AND15_OUT,,AND__BOOL__BOOL(
    (BOOL)__BOOL_LITERAL(TRUE),
    NULL,
    (UINT)2,
    (BOOL)__GET_VAR(data__->_TMP_NOT17_OUT,),
    (BOOL)__GET_VAR(data__->TRU,)));
  __SET_VAR(data__->TP2.,IN,,__GET_VAR(data__->TP0.Q,));
  __SET_VAR(data__->TP2.,PT,,__time_to_timespec(1, 3000, 0, 0, 0, 0));
  TP_body__(&data__->TP2);
  __SET_VAR(data__->,_TMP_AND16_OUT,,AND__BOOL__BOOL(
    (BOOL)__BOOL_LITERAL(TRUE),
    NULL,
    (UINT)2,
    (BOOL)__GET_VAR(data__->TP2.Q,),
    (BOOL)__GET_VAR(data__->TRU,)));
  __SET_VAR(data__->TOF0.,IN,,__GET_VAR(data__->TP1.Q,));
  __SET_VAR(data__->TOF0.,PT,,__time_to_timespec(1, 200, 0, 0, 0, 0));
  TOF_body__(&data__->TOF0);
  __SET_VAR(data__->,_TMP_NOT22_OUT,,!(__GET_VAR(data__->TOF0.Q,)));
  __SET_VAR(data__->TP1.,IN,,__GET_VAR(data__->_TMP_NOT22_OUT,));
  __SET_VAR(data__->TP1.,PT,,__time_to_timespec(1, 200, 0, 0, 0, 0));
  TP_body__(&data__->TP1);
  __SET_VAR(data__->,_TMP_AND26_OUT,,AND__BOOL__BOOL(
    (BOOL)__BOOL_LITERAL(TRUE),
    NULL,
    (UINT)2,
    (BOOL)__GET_VAR(data__->TP0.Q,),
    (BOOL)__GET_VAR(data__->TP1.Q,)));
  __SET_VAR(data__->,_TMP_OR27_OUT,,OR__BOOL__BOOL(
    (BOOL)__BOOL_LITERAL(TRUE),
    NULL,
    (UINT)2,
    (BOOL)__GET_VAR(data__->_TMP_AND16_OUT,),
    (BOOL)__GET_VAR(data__->_TMP_AND26_OUT,)));
  __SET_VAR(data__->,_TMP_OR20_OUT,,OR__BOOL__BOOL(
    (BOOL)__BOOL_LITERAL(TRUE),
    NULL,
    (UINT)2,
    (BOOL)__GET_VAR(data__->_TMP_AND15_OUT,),
    (BOOL)__GET_VAR(data__->_TMP_OR27_OUT,)));
  __SET_LOCATED(data__->,OUTB,,__GET_VAR(data__->_TMP_OR20_OUT,));
  __SET_LOCATED(data__->,OUTD,,__GET_VAR(data__->_TMP_OR27_OUT,));
  __SET_LOCATED(data__->,OUTA,,__GET_VAR(data__->_TMP_OR27_OUT,));
  __SET_LOCATED(data__->,OUTE,,__GET_VAR(data__->_TMP_OR27_OUT,));
  __SET_LOCATED(data__->,OUTG,,__GET_VAR(data__->_TMP_OR27_OUT,));
  __SET_LOCATED(data__->,OUTC,,__GET_VAR(data__->_TMP_AND15_OUT,));

  goto __end;

__end:
  return;
} // PROGRAM0_body__() 





